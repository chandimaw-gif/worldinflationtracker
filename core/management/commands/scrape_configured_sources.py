"""
Management command: scrape_configured_sources

Scrapes prices from configured ScrapeSource entries and saves them
as PriceObservation records.

Usage:
    python3 manage.py scrape_configured_sources
    python3 manage.py scrape_configured_sources --source keells
    python3 manage.py scrape_configured_sources --item "Rice Nadu"
    python3 manage.py scrape_configured_sources --dry-run
"""

import re
import time
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Country, PriceObservation, ScrapeSource, ScrapeLog

logger = logging.getLogger('scrapers')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 WorldInflationTracker/1.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def _extract_price(text, price_regex=None):
    """Extract numeric price from text."""
    if not text:
        return None
    text = str(text).strip().replace(',', '')

    if price_regex:
        match = re.search(price_regex, text)
        if match:
            text = match.group(1)
        else:
            return None
    else:
        match = re.search(r'([0-9]+(?:\.[0-9]+)?)', text.replace(',', ''))
        if match:
            text = match.group(1)
        else:
            return None

    try:
        val = Decimal(text)
        return val if val >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def _scrape_static(source):
    """Scrape a static HTML page using requests + BeautifulSoup."""
    resp = requests.get(source.url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    if source.selector_type == 'css':
        soup = BeautifulSoup(html, 'html.parser')
        el = soup.select_one(source.selector)
        if not el:
            raise Exception(f"CSS selector '{source.selector}' found no match")
        text = el.get_text(strip=True)
    elif source.selector_type == 'xpath':
        from lxml import html as lh
        tree = lh.fromstring(html)
        el = tree.xpath(source.selector)
        if not el:
            raise Exception(f"XPath '{source.selector}' found no match")
        text = el[0].text_content().strip() if hasattr(el[0], 'text_content') else str(el[0]).strip()
    elif source.selector_type == 'regex':
        match = re.search(source.selector, html)
        if not match:
            raise Exception(f"Regex '{source.selector}' found no match")
        text = match.group(1) if match.groups() else match.group(0)
    else:
        raise Exception(f"Unknown selector type: {source.selector_type}")

    price = _extract_price(text, source.price_regex or None)
    if price is None:
        raise Exception(f"Could not extract price from text: '{text[:200]}'")

    return price


def _scrape_js(source):
    """Scrape a JavaScript-rendered page using Playwright."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS['User-Agent'])
        page.goto(source.url, timeout=60000)
        page.wait_for_timeout(5000)

        if source.selector_type == 'css':
            el = page.query_selector(source.selector)
            if not el:
                browser.close()
                raise Exception(f"CSS selector '{source.selector}' found no match")
            text = el.inner_text()
        elif source.selector_type == 'xpath':
            el = page.query_selector(f'xpath={source.selector}')
            if not el:
                browser.close()
                raise Exception(f"XPath '{source.selector}' found no match")
            text = el.inner_text()
        elif source.selector_type == 'regex':
            html = page.content()
            match = re.search(source.selector, html)
            if not match:
                browser.close()
                raise Exception(f"Regex '{source.selector}' found no match")
            text = match.group(1) if match.groups() else match.group(0)
        else:
            browser.close()
            raise Exception(f"Unknown selector type: {source.selector_type}")

        browser.close()

    price = _extract_price(text, source.price_regex or None)
    if price is None:
        raise Exception(f"Could not extract price from text: '{text[:200]}'")

    return price


class Command(BaseCommand):
    help = 'Scrape prices from configured ScrapeSource entries'

    def add_arguments(self, parser):
        parser.add_argument('--country', type=str, default='LKA', help='ISO country code')
        parser.add_argument('--source', type=str, help='Filter by source name substring')
        parser.add_argument('--item', type=str, help='Filter by item name substring')
        parser.add_argument('--dry-run', action='store_true', help='Do not save prices')
        parser.add_argument('--force', action='store_true', help='Overwrite existing observations for today')
        parser.add_argument('--limit', type=int, help='Limit number of sources to scrape')

    def handle(self, *args, **options):
        try:
            country = Country.objects.get(code=options['country'], is_active=True)
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Country {options['country']} not found"))
            return

        qs = ScrapeSource.objects.filter(country=country, is_active=True)

        if options.get('source'):
            qs = qs.filter(source_name__icontains=options['source'])
        if options.get('item'):
            qs = qs.filter(item__name__icontains=options['item'])

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No active scrape sources found"))
            return

        if options.get('limit'):
            qs = qs[:options['limit']]
            total = options['limit']

        self.stdout.write(f"Scraping {total} configured source(s)...")

        success_count = 0
        fail_count = 0
        today = date.today()
        run_errors = []

        for source in qs:
            self.stdout.write(f"\n  -> {source.item.name} from {source.source_name}")

            try:
                if source.requires_js:
                    price = _scrape_js(source)
                else:
                    price = _scrape_static(source)

                final_price = (price * source.price_multiplier).quantize(Decimal('0.01'))

                self.stdout.write(self.style.SUCCESS(
                    f"    OK Price: {final_price} {source.currency_code} (raw: {price})"
                ))

                if not options['dry_run']:
                    PriceObservation.objects.update_or_create(
                        item=source.item,
                        country=country,
                        observation_date=today,
                        defaults={
                            'price': final_price,
                            'currency_code': source.currency_code,
                            'source_url': source.url,
                            'source_name': source.source_name,
                            'scrape_method': 'automated',
                            'raw_data': {
                                'scrape_source_id': source.id,
                                'raw_price': str(price),
                                'multiplier': str(source.price_multiplier),
                                'selector': source.selector,
                            },
                        }
                    )

                source.last_price = final_price
                source.last_price_date = today
                source.last_status = 'success'
                source.last_error = ''
                source.last_scraped_at = timezone.now()
                if not options['dry_run']:
                    source.save(update_fields=[
                        'last_price', 'last_price_date', 'last_status',
                        'last_error', 'last_scraped_at'
                    ])

                success_count += 1

            except Exception as e:
                error_msg = str(e)
                self.stdout.write(self.style.ERROR(f"    FAILED: {error_msg}"))
                source.last_status = 'failed'
                source.last_error = error_msg[:500]
                source.last_scraped_at = timezone.now()
                if not options['dry_run']:
                    source.save(update_fields=['last_status', 'last_error', 'last_scraped_at'])
                fail_count += 1
                run_errors.append(f"{source.item.name} ({source.source_name}): {error_msg}")

            time.sleep(2)

        if not options['dry_run']:
            ScrapeLog.objects.create(
                job_name='scrape_configured_sources',
                country=country,
                started_at=timezone.now(),
                completed_at=timezone.now(),
                status='success' if fail_count == 0 else ('partial' if success_count > 0 else 'failed'),
                items_scraped=success_count,
                items_failed=fail_count,
                error_log='\n'.join(run_errors)[:2000],
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Success: {success_count}, Failed: {fail_count}"
        ))

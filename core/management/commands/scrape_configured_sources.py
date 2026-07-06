"""
Scrape prices from configured ScrapeSource entries.

Usage:
    python manage.py scrape_configured_sources --country LKA
    python manage.py scrape_configured_sources --source "Keells"
    python manage.py scrape_configured_sources --item "Rice" --dry-run
"""

import json
import logging
import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import BasketItem, Country, PriceObservation, PriceAuditLog, ScrapeLog, ScrapeSource

logger = logging.getLogger('scrapers')


class Command(BaseCommand):
    help = 'Scrape prices from configured ScrapeSource entries'

    def add_arguments(self, parser):
        parser.add_argument('--country', default='LKA', help='ISO 3166-1 alpha-3 country code')
        parser.add_argument('--source', help='Filter by source name substring')
        parser.add_argument('--item', help='Filter by basket item name substring')
        parser.add_argument('--dry-run', action='store_true', help='Do not save to database')
        parser.add_argument('--force', action='store_true', help='Ignore frequency checks')
        parser.add_argument('--limit', type=int, help='Limit number of sources processed')

    def handle(self, *args, **options):
        self.country_code = options['country']
        self.dry_run = options['dry_run']
        self.force = options['force']

        country = Country.objects.filter(code=self.country_code).first()
        if not country:
            self.stderr.write(self.style.ERROR(f"Country {self.country_code} not found"))
            return

        qs = ScrapeSource.objects.filter(
            item__country__code=self.country_code,
            is_active=True,
        ).select_related('item', 'item__country').order_by('source_name')

        if options['source']:
            qs = qs.filter(source_name__icontains=options['source'])
        if options['item']:
            qs = qs.filter(item__name__icontains=options['item'])
        if options['limit']:
            qs = qs[:options['limit']]

        if not qs.exists():
            self.stdout.write(self.style.WARNING("No active ScrapeSource entries match the filters."))
            return

        scrape_log = ScrapeLog.objects.create(
            job_name='scrape_configured_sources',
            country=country,
            started_at=timezone.now(),
            status='running',
            source_url='',
        )

        items_scraped = 0
        items_failed = 0
        errors: list[str] = []

        session = requests.Session()
        session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
        })

        for source in qs:
            try:
                result = self._scrape_source(source, session)
                if result.get('success'):
                    items_scraped += 1
                    if not self.dry_run:
                        self._save_price(source, result)
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[DRY-RUN] {source.source_name}: {result['price']} LKR "
                                f"(raw: {result.get('raw_text', '')})"
                            )
                        )
                else:
                    items_failed += 1
                    err = result.get('error', 'Unknown error')
                    errors.append(f"{source.source_name}: {err}")
                    self._update_source_status(source, 'failed', error=err)
                    self.stdout.write(self.style.ERROR(f"{source.source_name}: {err}"))
            except Exception as exc:
                items_failed += 1
                err = str(exc)
                errors.append(f"{source.source_name}: {err}")
                self._update_source_status(source, 'failed', error=err)
                logger.exception(f"Failed to scrape {source.source_name}")
                self.stdout.write(self.style.ERROR(f"{source.source_name}: {err}"))

            # Respectful rate limit between requests
            time.sleep(1.5)

        status = 'success'
        if items_failed > 0 and items_scraped == 0:
            status = 'failed'
        elif items_failed > 0:
            status = 'partial'

        scrape_log.completed_at = timezone.now()
        scrape_log.status = status
        scrape_log.items_scraped = items_scraped
        scrape_log.items_failed = items_failed
        scrape_log.error_log = '\n'.join(errors)
        scrape_log.save()

        self.stdout.write(
            f"Done. Scraped: {items_scraped}, Failed: {items_failed}, Status: {status}"
        )

    def _scrape_source(self, source: ScrapeSource, session: requests.Session) -> Dict[str, Any]:
        """Fetch and parse a single source. Returns dict with success/price/error."""
        url = source.url
        if not url.startswith('http'):
            url = 'https://' + url

        today = date.today()

        # Frequency check: skip if already scraped successfully today
        if not self.force and source.last_scraped_at and source.last_scraped_at.date() == today:
            if source.last_status == 'success':
                return {
                    'success': False,
                    'error': 'Already scraped successfully today (use --force to override)',
                }

        if source.selector_type == 'shopify':
            return self._scrape_shopify(source, session)

        if source.selector_type == 'ceypetco_fuel':
            return self._scrape_ceypetco_fuel(source, session)

        if source.requires_js:
            return self._scrape_with_playwright(source, url)

        return self._scrape_static(source, url, session)

    def _fetch_static(self, url: str, session: requests.Session) -> str:
        """Fetch static HTML with redirect following and proper headers."""
        response = session.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response.text

    def _scrape_static(self, source: ScrapeSource, url: str, session: requests.Session) -> Dict[str, Any]:
        html = self._fetch_static(url, session)

        if source.selector_type == 'css':
            soup = BeautifulSoup(html, 'html.parser')
            elements = soup.select(source.selector)
            if not elements:
                return {'success': False, 'error': f"CSS selector returned no results: {source.selector}"}
            raw_text = ' '.join(el.get_text(strip=True) for el in elements[:5])

        elif source.selector_type == 'xpath':
            try:
                from lxml import html as lh
            except ImportError:
                return {'success': False, 'error': 'lxml is required for XPath selectors'}
            tree = lh.fromstring(html)
            elements = tree.xpath(source.selector)
            if not elements:
                return {'success': False, 'error': f"XPath returned no results: {source.selector}"}
            raw_text = ' '.join(
                el.text_content().strip() if hasattr(el, 'text_content') else str(el).strip()
                for el in elements[:5]
            )

        elif source.selector_type == 'regex':
            match = re.search(source.selector, html, re.IGNORECASE | re.DOTALL)
            if not match:
                return {'success': False, 'error': f"Regex returned no results: {source.selector}"}
            raw_text = match.group(1) if match.groups() else match.group(0)

        elif source.selector_type == 'json':
            data = json.loads(html)
            raw_text = self._json_path_get(data, source.selector)
            if raw_text is None:
                return {'success': False, 'error': f"JSON path returned no results: {source.selector}"}

        else:
            return {'success': False, 'error': f"Unsupported selector type: {source.selector_type}"}

        price = self._extract_price(raw_text, source.price_regex)
        if price is None:
            return {'success': False, 'error': f"Could not extract price from: {raw_text[:200]}"}

        return {
            'success': True,
            'price': price,
            'raw_text': raw_text,
        }

    def _scrape_shopify(self, source: ScrapeSource, session: requests.Session) -> Dict[str, Any]:
        """Parse Shopify product JSON endpoint."""
        url = source.url
        parsed = urlparse(url)
        path = parsed.path
        if not path.endswith('.json'):
            # Convert handle URL to JSON endpoint
            if '/products/' in path:
                handle = path.split('/products/')[-1].split('/')[0]
                path = f'/products/{handle}.json'
            else:
                return {'success': False, 'error': 'Invalid Shopify URL; expected /products/{handle}.json'}
            url = urljoin(url, path)

        try:
            data = session.get(url, timeout=30).json()
        except Exception as exc:
            return {'success': False, 'error': f"Failed to fetch Shopify JSON: {exc}"}

        product = data.get('product', {})
        variants = product.get('variants', [])
        if not variants:
            return {'success': False, 'error': 'No variants found in Shopify product'}

        selected_variant = None
        if source.selector:
            # selector holds a variant title fragment (case-insensitive)
            fragment = source.selector.lower()
            for variant in variants:
                variant_title = (variant.get('title') or '').lower()
                if fragment in variant_title:
                    selected_variant = variant
                    break
            if not selected_variant:
                # Try matching numeric weight fragment (e.g. "1000" for 1kg)
                for variant in variants:
                    if fragment in (variant.get('option1') or '').lower() or \
                       fragment in (variant.get('option2') or '').lower():
                        selected_variant = variant
                        break

        # Fallback to first available variant, else first variant
        if not selected_variant:
            for variant in variants:
                if variant.get('available', True):
                    selected_variant = variant
                    break
            if not selected_variant:
                selected_variant = variants[0]

        raw_text = selected_variant.get('price')
        if raw_text is None:
            return {'success': False, 'error': 'Selected Shopify variant has no price'}

        price = self._extract_price(str(raw_text), source.price_regex)
        if price is None:
            return {'success': False, 'error': f"Could not parse Shopify price: {raw_text}"}

        return {
            'success': True,
            'price': price,
            'raw_text': str(raw_text),
        }

    def _scrape_ceypetco_fuel(self, source: ScrapeSource, session: requests.Session) -> Dict[str, Any]:
        """Parse the first fuel price table on CEYPETCO historical prices page."""
        url = 'https://ceypetco.gov.lk/historical-prices/'
        html = self._fetch_static(url, session)

        table_re = re.compile(r'<table[^>]*>(.*?)</table>', re.IGNORECASE | re.DOTALL)
        row_re = re.compile(r'<tr>\s*<td>(\d{2}\.\d{2}\.\d{4})</td>((?:\s*<td>([^<]*)</td>)*)\s*</tr>', re.IGNORECASE | re.DOTALL)
        cell_re = re.compile(r'<td>([^<]*)</td>', re.IGNORECASE)
        header_re = re.compile(r'<th>([^<]*)</th>', re.IGNORECASE)

        best_table = None
        best_headers = None

        for table_match in table_re.finditer(html):
            table_html = table_match.group(1)
            headers = [h.strip() for h in header_re.findall(table_html)]
            header_text = ' '.join(headers).upper()
            if 'CIRCULAR' in header_text or 'DRUM' in header_text:
                continue
            if any(x in header_text for x in ['LP 92', 'LP 95', 'LAD']):
                best_table = table_html
                best_headers = headers
                break

        if not best_table or not best_headers:
            return {'success': False, 'error': 'CEYPETCO fuel table not found'}

        rows = row_re.findall(best_table)
        if not rows:
            return {'success': False, 'error': 'No data rows in CEYPETCO fuel table'}

        date_str = rows[0][0]
        cell_values = [v.strip() for v in cell_re.findall(rows[0][1])]

        # source.selector is the column name fragment, e.g. "LP 92"
        target_col = (source.selector or '').strip()
        if not target_col:
            return {'success': False, 'error': 'No CEYPETCO column selector configured'}

        price = None
        for i, val in enumerate(cell_values):
            if i + 1 >= len(best_headers):
                break
            header = best_headers[i + 1]
            if target_col.upper() in header.upper():
                price = self._extract_price(val)
                if price and price > 0:
                    break

        if price is None:
            return {
                'success': False,
                'error': f"CEYPETCO column '{target_col}' not found or empty. Headers: {best_headers}",
            }

        return {
            'success': True,
            'price': price,
            'raw_text': f"{date_str} {target_col}={price}",
        }

    def _scrape_with_playwright(self, source: ScrapeSource, url: str) -> Dict[str, Any]:
        """Render JavaScript with Playwright and extract price."""
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            return {'success': False, 'error': 'playwright is not installed'}

        raw_text = ''
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0 Chrome/125.0.0.0 Safari/537.0'
                )
                page = context.new_page()
                page.goto(url, wait_until='networkidle', timeout=45000)

                # Wait a moment for React/SPA hydration
                page.wait_for_timeout(3000)

                if source.selector:
                    try:
                        page.wait_for_selector(source.selector, timeout=10000)
                        elements = page.locator(source.selector).all()
                        raw_text = ' '.join(el.inner_text().strip() for el in elements[:5] if el.is_visible())
                    except PWTimeout:
                        raw_text = ''

                if not raw_text:
                    # Fallback: search the page text for price patterns
                    raw_text = page.locator('body').inner_text()

                browser.close()
        except Exception as exc:
            return {'success': False, 'error': f"Playwright failed: {exc}"}

        price = self._extract_price(raw_text, source.price_regex)
        if price is None:
            return {'success': False, 'error': f"Could not extract price from rendered page: {raw_text[:200]}"}

        return {
            'success': True,
            'price': price,
            'raw_text': raw_text[:500],
        }

    def _extract_price(self, text: Any, price_regex: str = '') -> Optional[Decimal]:
        """Extract a positive numeric price from text."""
        if text is None:
            return None
        text = str(text).strip()

        if price_regex:
            match = re.search(price_regex, text, re.IGNORECASE)
            if match:
                candidate = match.group(1) if match.groups() else match.group(0)
                text = candidate
            else:
                return None

        # Remove currency symbols, commas, spaces
        cleaned = re.sub(r'[RsLKR₹$€£\s,]', '', text)
        match = re.search(r'\d+\.?\d*', cleaned)
        if match:
            try:
                price = Decimal(match.group())
                return price if price > 0 else None
            except InvalidOperation:
                return None
        return None

    def _json_path_get(self, data: Any, path: str) -> Any:
        """Simple dotted JSON path accessor. Supports array indexes, e.g. 'product.variants.0.price'."""
        if not path:
            return data
        current = data
        for part in path.split('.'):
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def _save_price(self, source: ScrapeSource, result: Dict[str, Any]) -> None:
        """Save the scraped price and audit trail."""
        price = result['price']
        multiplier = source.price_multiplier or Decimal('1')
        if multiplier != Decimal('1'):
            price = (price * multiplier).quantize(Decimal('0.01'))

        country = source.item.country
        today = date.today()

        with transaction.atomic():
            obs, created = PriceObservation.objects.update_or_create(
                item=source.item,
                country=country,
                observation_date=today,
                defaults={
                    'price': price,
                    'currency_code': source.currency_code or country.currency_code,
                    'source_url': source.url,
                    'source_name': source.source_name,
                    'scrape_method': 'automated',
                    'raw_data': {
                        'selector_type': source.selector_type,
                        'selector': source.selector,
                        'raw_text': result.get('raw_text', ''),
                        'multiplier': str(multiplier),
                    },
                    'is_validated': False,
                }
            )

            PriceAuditLog.objects.create(
                item=source.item,
                country=country,
                observation_date=today,
                price=price,
                source_url=source.url,
                source_name=source.source_name,
                scrape_method='automated',
                product_page_title=source.source_name,
                product_page_snapshot=self._json_safe(result),
            )

        self._update_source_status(source, 'success', price=price)
        action = 'Created' if created else 'Updated'
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} PriceObservation: {source.item.name} @ {price} LKR ({source.source_name})"
            )
        )

    def _json_safe(self, obj: Any) -> Any:
        """Recursively convert Decimal values to strings for JSON storage."""
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, dict):
            return {k: self._json_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._json_safe(v) for v in obj]
        return obj

    def _update_source_status(self, source: ScrapeSource, status: str, price: Optional[Decimal] = None, error: str = '') -> None:
        source.last_status = status
        source.last_scraped_at = timezone.now()
        if price is not None:
            source.last_price = price
        if error:
            source.last_error = error[:1000]
        source.save(update_fields=['last_status', 'last_scraped_at', 'last_price', 'last_error'])

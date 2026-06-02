"""
Management command: import_sheet_news

Reads the 'News' tab from the WIT Google Sheet and imports articles
into the NewsArticle model. These articles take priority over RSS-scraped ones.

Sheet format (News tab):
  Col A: Date (e.g. 01/06/2026)
  Col B: Source (e.g. "CBSL (cbsl.gov.lk)")
  Col C: Headline
  Col D: Synopsis
  Col E: Link

Usage:
    python3 manage.py import_sheet_news
    python3 manage.py import_sheet_news --dry-run
"""

import csv
import io
import re
import logging
from datetime import datetime

import requests
from django.core.management.base import BaseCommand
from django.conf import settings

from core.models import Country, NewsArticle

logger = logging.getLogger('scrapers')

HEADERS = {'User-Agent': 'Mozilla/5.0 WorldInflationTracker/1.0'}

CATEGORY_KEYWORDS = {
    'policy': ['cbsl', 'central bank', 'policy rate', 'monetary', 'imf', 'budget',
               'government', 'ministry', 'parliament', 'fiscal', 'tax'],
    'markets': ['exchange rate', 'usd', 'lkr', 'rupee', 'stock', 'cse', 'bond',
                'forex', 'gold price', 'oil price', 'interest rate'],
    'international': ['global', 'world', 'china', 'india', 'usa', 'fed', 'opec',
                      'international', 'export', 'import'],
}


def classify_category(title, synopsis):
    text = (title + ' ' + synopsis).lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return cat
    return 'economy'


def clean_source_name(raw):
    """Extract clean source name from format like 'CBSL (cbsl.gov.lk)'"""
    if not raw:
        return raw
    match = re.match(r'^([^(]+)', raw.strip())
    return match.group(1).strip() if match else raw.strip()


class Command(BaseCommand):
    help = 'Import curated news articles from WIT Google Sheet News tab'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str,
                            help='Published CSV URL for News tab')
        parser.add_argument('--country', type=str, default='LKA')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            country = Country.objects.get(code=options['country'], is_active=True)
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Country {options['country']} not found"))
            return

        csv_url = (options.get('url') or
                   getattr(settings, 'NEWS_SHEET_CSV_URL', ''))
        if not csv_url:
            self.stderr.write(self.style.ERROR(
                "No URL provided. Set NEWS_SHEET_CSV_URL in settings."
            ))
            return

        self.stdout.write("Fetching news from Google Sheet...")
        try:
            resp = requests.get(csv_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            rows = list(csv.reader(io.StringIO(resp.text)))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch: {e}"))
            return

        self.stdout.write(f"Downloaded {len(rows)} rows.")

        created = 0
        updated = 0

        for row in rows[1:]:  # Skip header
            if len(row) < 5:
                continue

            date_str = row[0].strip()
            source_raw = row[1].strip()
            headline = row[2].strip()
            synopsis = row[3].strip()
            link = row[4].strip()

            if not headline or not link:
                continue

            source_name = clean_source_name(source_raw)
            category = classify_category(headline, synopsis)

            # Parse date
            published_dt = None
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']:
                try:
                    published_dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    pass

            if options.get('dry_run'):
                self.stdout.write(
                    f"  [DRY RUN] {source_name}: {headline[:60]}"
                )
                continue

            # Sheet articles marked as is_featured=True (priority over RSS)
            obj, was_created = NewsArticle.objects.update_or_create(
                source_url=link,
                defaults={
                    'country': country,
                    'title': headline,
                    'summary': synopsis,
                    'source_name': source_name,
                    'published_at': published_dt,
                    'category': category,
                    'is_featured': True,
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Created: {created}, Updated: {updated} sheet news articles."
        ))

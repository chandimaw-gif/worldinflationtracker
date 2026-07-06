"""
Management command: import_usd_lkr_rate

Reads the 'USD to LKR' tab from the WIT Google Sheet and updates
the CBSL TT selling rate displayed on the homepage.

Sheet format (USD to LKR tab):
  Row 1: Headers — "Bank (Selling Rate)", date1, date2, ...
  Row 2: "CBSL TT Selling Rate", rate1, rate2, ...

Usage:
    python3 manage.py import_usd_lkr_rate
    python3 manage.py import_usd_lkr_rate --dry-run
"""

import csv
import io
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

import requests
from django.core.management.base import BaseCommand
from django.conf import settings

from core.models import Country, ExchangeRate

logger = logging.getLogger('scrapers')
HEADERS = {'User-Agent': 'Mozilla/5.0 WorldInflationTracker/1.0'}


def _parse_date(text):
    text = str(text).strip()
    for fmt in ['%d-%b-%y', '%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y']:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _parse_decimal(text):
    if not text:
        return None
    clean = str(text).strip().replace(',', '')
    if not clean or clean in ('-', 'N/A'):
        return None
    try:
        val = Decimal(clean)
        return val if val > 0 else None
    except InvalidOperation:
        return None


class Command(BaseCommand):
    help = 'Import CBSL TT USD/LKR rate from WIT Google Sheet USD to LKR tab'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str)
        parser.add_argument('--country', type=str, default='LKA')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            country = Country.objects.get(code=options['country'], is_active=True)
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Country {options['country']} not found"))
            return

        csv_url = (options.get('url') or
                   getattr(settings, 'USD_LKR_SHEET_CSV_URL', ''))
        if not csv_url:
            self.stderr.write(self.style.ERROR(
                "No URL. Set USD_LKR_SHEET_CSV_URL in settings."
            ))
            return

        self.stdout.write("Fetching USD/LKR rates from Google Sheet...")
        try:
            resp = requests.get(csv_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            rows = list(csv.reader(io.StringIO(resp.text)))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch: {e}"))
            return

        if len(rows) < 2:
            self.stderr.write(self.style.ERROR("Sheet has no data rows"))
            return

        # Row 0 = headers: "Bank (Selling Rate)", date1, date2 ...
        # Row 1 = "CBSL TT Selling Rate", rate1, rate2 ...
        header = rows[0]
        data_row = None
        for row in rows[1:]:
            if row and 'CBSL' in row[0].upper():
                data_row = row
                break

        if not data_row:
            self.stderr.write(self.style.ERROR("CBSL TT row not found in sheet"))
            return

        saved = 0
        for i, date_str in enumerate(header[1:], start=1):
            rate_date = _parse_date(date_str)
            if not rate_date:
                continue
            rate_value = _parse_decimal(data_row[i]) if i < len(data_row) else None
            if not rate_value:
                continue

            if options.get('dry_run'):
                self.stdout.write(f"  [DRY RUN] {rate_date}: USD/LKR = {rate_value}")
                continue

            ExchangeRate.objects.update_or_create(
                country=country,
                base_currency='USD',
                rate_date=rate_date,
                defaults={
                    'rate': rate_value,
                    'local_currency': 'LKR',
                    'source': 'CBSL TT (Google Sheet)',
                }
            )
            saved += 1

        if not options.get('dry_run'):
            self.stdout.write(self.style.SUCCESS(
                f"Saved {saved} USD/LKR rate records."
            ))

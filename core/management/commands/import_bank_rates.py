"""
Management command: import_bank_rates

Reads the 'Bank Exchange Rates' tab from the WIT Google Sheets CSV
and saves rates into BankExchangeRate for display on the exchange rates page.

The sheet has date blocks, each with rows per bank and columns per currency.
Format: [marker] [date] [bank_name] [USD_buy] [USD_sell] [GBP_buy] [GBP_sell] ...

Usage:
    python3 manage.py import_bank_rates
    python3 manage.py import_bank_rates --url "https://docs.google.com/..."
    python3 manage.py import_bank_rates --dry-run
"""

import csv
import io
import re
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

import requests
from django.core.management.base import BaseCommand
from django.conf import settings

from core.models import Country, BankExchangeRate

logger = logging.getLogger('scrapers')

CURRENCIES = ["USD", "GBP", "EUR", "AUD", "CAD", "SGD", "JPY", "INR"]

KNOWN_BANKS = [
    "Commercial Bank",
    "HNB (Hatton National Bank)",
    "Sampath Bank",
    "Bank of Ceylon (BOC)",
    "People's Bank",
    "DFCC Bank",
    "Seylan Bank",
    "NDB Bank",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 WorldInflationTracker/1.0'}


def _parse_decimal(text):
    if not text:
        return None
    clean = str(text).strip().replace(',', '').replace(' ', '')
    if not clean or clean in ('-', 'N/A', '#'):
        return None
    try:
        val = Decimal(clean)
        return val if val > 0 else None
    except InvalidOperation:
        return None


def _parse_date(text):
    if not text:
        return None
    text = str(text).strip()
    for fmt in ['%Y-%m-%d', '%d-%b-%y', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d %B %Y']:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


class Command(BaseCommand):
    help = 'Import bank exchange rates from Google Sheets Bank Exchange Rates tab'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, help='Google Sheets CSV URL for bank rates tab')
        parser.add_argument('--country', type=str, default='LKA')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force', action='store_true', help='Overwrite existing records')

    def handle(self, *args, **options):
        try:
            country = Country.objects.get(code=options['country'], is_active=True)
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Country {options['country']} not found"))
            return

        # Get URL — try settings first, then --url arg
        csv_url = options.get('url') or getattr(settings, 'BANK_RATES_SHEET_CSV_URL', '')
        if not csv_url:
            self.stderr.write(self.style.ERROR(
                "No CSV URL provided. Set BANK_RATES_SHEET_CSV_URL in settings "
                "or pass --url 'https://...'"
            ))
            return

        self.stdout.write("Fetching bank rates from Google Sheets...")
        try:
            resp = requests.get(csv_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            rows = list(csv.reader(io.StringIO(resp.text)))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch: {e}"))
            return

        self.stdout.write(f"Downloaded {len(rows)} rows. Parsing...")

        records = self._parse_bank_rates(rows)
        if not records:
            self.stderr.write(self.style.WARNING("No bank rate records found in sheet."))
            return

        self.stdout.write(f"Found {len(records)} rate records.")

        if options.get('dry_run'):
            for r in records[:10]:
                self.stdout.write(
                    f"  [DRY RUN] {r['date']} {r['bank']} {r['currency']}: "
                    f"Buy={r['buying']} Sell={r['selling']}"
                )
            return

        saved = 0
        for r in records:
            try:
                _, created = BankExchangeRate.objects.update_or_create(
                    country=country,
                    bank_name=r['bank'],
                    rate_date=r['date'],
                    currency=r['currency'],
                    defaults={
                        'buying_rate': r['buying'],
                        'selling_rate': r['selling'],
                        'tt_buying_rate': r['buying'],
                        'tt_selling_rate': r['selling'],
                        'source_url': csv_url,
                    }
                )
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save {r}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Saved {saved} bank rate records."))

    def _parse_bank_rates(self, rows):
        """
        Parse the bank rates sheet.
        Looks for rows where column B is a valid date and column C is a known bank name.
        """
        records = []

        for row in rows:
            if len(row) < 4:
                continue

            # Skip header/title rows
            bank_name = row[2].strip() if len(row) > 2 else ''
            if not bank_name or bank_name == 'Bank':
                continue

            # Check if this is a bank data row (col C matches a known bank)
            matched_bank = None
            for b in KNOWN_BANKS:
                if b.lower() in bank_name.lower() or bank_name.lower() in b.lower():
                    matched_bank = b
                    break

            if not matched_bank:
                continue

            # Parse date from column B
            rate_date = _parse_date(row[1]) if len(row) > 1 else None
            if not rate_date:
                continue

            # Parse currency pairs starting from column D (index 3)
            # Format: USD_buy, USD_sell, GBP_buy, GBP_sell, ...
            for i, curr in enumerate(CURRENCIES):
                buy_idx = 3 + i * 2
                sell_idx = 4 + i * 2

                buying = _parse_decimal(row[buy_idx]) if buy_idx < len(row) else None
                selling = _parse_decimal(row[sell_idx]) if sell_idx < len(row) else None

                if buying or selling:
                    records.append({
                        'bank': matched_bank,
                        'date': rate_date,
                        'currency': curr,
                        'buying': buying,
                        'selling': selling,
                    })

        return records

"""
Management command: import_google_sheet_rates

Reads the 'Exchange Rates' tab from the WIT Google Sheet (published as CSV)
and saves bank buy/sell rates into BankExchangeRate.

Sheet format (Exchange Rates tab):
  Col A: Bank name (or blank for continuation rows)
  Col B: Currency label (e.g. "USD Buy", "USD Sell", "GBP Buy" etc.)
  Col C onwards: Date columns (e.g. "31-May-26", "01-Jun-26" ...)

Usage:
    python3 manage.py import_google_sheet_rates
    python3 manage.py import_google_sheet_rates --url "https://..."
    python3 manage.py import_google_sheet_rates --dry-run
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

HEADERS = {'User-Agent': 'Mozilla/5.0 WorldInflationTracker/1.0'}

# Sanity check bounds for LKR rates — flag clearly wrong values
RATE_BOUNDS = {
    'USD': (250, 400),
    'GBP': (300, 550),
    'EUR': (270, 480),
    'AUD': (150, 300),
    'CAD': (170, 320),
    'SGD': (170, 320),
    'JPY': (1.5, 3.5),
    'INR': (2.5, 5.5),
}


def _parse_decimal(text):
    if not text:
        return None
    clean = str(text).strip().replace(',', '').replace(' ', '')
    if not clean or clean in ('-', 'N/A', '#', ''):
        return None
    try:
        val = Decimal(clean)
        return val if val > 0 else None
    except InvalidOperation:
        return None


def _parse_date(text):
    text = str(text).strip()
    for fmt in ['%d-%b-%y', '%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _is_valid_rate(currency, value):
    """Check if rate is within expected bounds for LKR."""
    if value is None:
        return False
    bounds = RATE_BOUNDS.get(currency)
    if not bounds:
        return True
    return bounds[0] <= float(value) <= bounds[1]


class Command(BaseCommand):
    help = 'Import bank exchange rates from WIT Google Sheet (Exchange Rates tab)'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str,
                            help='Published CSV URL for Exchange Rates tab')
        parser.add_argument('--country', type=str, default='LKA')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        try:
            country = Country.objects.get(code=options['country'], is_active=True)
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Country {options['country']} not found"))
            return

        csv_url = options.get('url') or getattr(settings, 'EXCHANGE_RATES_SHEET_CSV_URL', '')
        if not csv_url:
            self.stderr.write(self.style.ERROR(
                "No URL provided. Set EXCHANGE_RATES_SHEET_CSV_URL in settings "
                "or pass --url 'https://...'"
            ))
            return

        self.stdout.write("Fetching exchange rates from Google Sheet...")
        try:
            resp = requests.get(csv_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            rows = list(csv.reader(io.StringIO(resp.text)))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch: {e}"))
            return

        self.stdout.write(f"Downloaded {len(rows)} rows.")

        # Parse date columns from header row (row 0)
        # Format: Bank | currency_label | date1 | date2 | ...
        if not rows:
            self.stderr.write(self.style.ERROR("Empty sheet"))
            return

        header = rows[0]
        date_cols = {}  # col_index → date
        for i, cell in enumerate(header[2:], start=2):
            d = _parse_date(cell)
            if d:
                date_cols[i] = d

        if not date_cols:
            self.stderr.write(self.style.ERROR(
                f"No date columns found in header: {header[:8]}"
            ))
            return

        self.stdout.write(
            f"Found {len(date_cols)} date columns: "
            f"{min(date_cols.values())} to {max(date_cols.values())}"
        )

        # Parse data rows
        records = []
        warnings = []
        current_bank = None

        for row in rows[1:]:
            if not row or len(row) < 3:
                continue

            # Bank name in col A (may be blank for continuation rows)
            if row[0].strip():
                current_bank = row[0].strip()

            if not current_bank:
                continue

            # Currency label in col B: "USD Buy", "USD Sell", "GBP Buy" etc.
            label = row[1].strip() if len(row) > 1 else ''
            if not label:
                continue

            # Parse currency and direction from label
            match = re.match(r'^(USD|GBP|EUR|AUD|CAD|SGD|JPY|INR)\s+(Buy|Sell)$',
                             label, re.IGNORECASE)
            if not match:
                continue

            currency = match.group(1).upper()
            direction = match.group(2).lower()  # 'buy' or 'sell'

            # Read values for each date column
            for col_idx, rate_date in date_cols.items():
                if col_idx >= len(row):
                    continue
                value = _parse_decimal(row[col_idx])
                if value is None:
                    continue

                if not _is_valid_rate(currency, value):
                    warnings.append(
                        f"  ⚠️  {current_bank} {currency} {direction} "
                        f"on {rate_date}: {value} — out of expected range, skipped"
                    )
                    continue

                records.append({
                    'bank': current_bank,
                    'date': rate_date,
                    'currency': currency,
                    'direction': direction,
                    'value': value,
                })

        # Print warnings
        if warnings:
            self.stdout.write(self.style.WARNING(f"\n{len(warnings)} suspicious values skipped:"))
            for w in warnings:
                self.stdout.write(w)

        if not records:
            self.stderr.write(self.style.ERROR("No valid rate records found."))
            return

        self.stdout.write(f"\nFound {len(records)} valid rate records.")

        if options.get('dry_run'):
            for r in records[:12]:
                self.stdout.write(
                    f"  [DRY RUN] {r['date']} | {r['bank']} | "
                    f"{r['currency']} {r['direction']}: {r['value']}"
                )
            return

        # Group by bank+date+currency and save
        # Build a dict: (bank, date, currency) → {buy, sell}
        grouped = {}
        for r in records:
            key = (r['bank'], r['date'], r['currency'])
            if key not in grouped:
                grouped[key] = {'buying': None, 'selling': None}
            if r['direction'] == 'buy':
                grouped[key]['buying'] = r['value']
            else:
                grouped[key]['selling'] = r['value']

        saved = 0
        for (bank, rate_date, currency), rates in grouped.items():
            try:
                BankExchangeRate.objects.update_or_create(
                    country=country,
                    bank_name=bank,
                    rate_date=rate_date,
                    currency=currency,
                    defaults={
                        'buying_rate': rates['buying'],
                        'selling_rate': rates['selling'],
                        'tt_buying_rate': rates['buying'],
                        'tt_selling_rate': rates['selling'],
                        'source_url': csv_url,
                    }
                )
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save {bank} {currency} {rate_date}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"Saved {saved} bank rate records across "
            f"{len(set(k[0] for k in grouped))} banks."
        ))

"""
Management command: import_wit_prices

Reads the WIT Real-World Price Sheet from a published Google Sheets CSV URL,
loads prices into PriceObservation, then recomputes the WIT headline CPI
so the chart updates automatically.

Setup:
  1. Publish Google Sheet as CSV (File → Share → Publish to web → CSV)
  2. Set PRICE_SHEET_CSV_URL in your .env file
  3. Run: python3 manage.py import_wit_prices
  4. Optionally schedule via Celery to run monthly

Usage:
    python3 manage.py import_wit_prices
    python3 manage.py import_wit_prices --url "https://docs.google.com/..."
    python3 manage.py import_wit_prices --dry-run
    python3 manage.py import_wit_prices --recompute-only
"""

import csv
import io
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from dateutil.relativedelta import relativedelta

from core.models import Country, BasketItem, PriceObservation, CPIIndex

logger = logging.getLogger('scrapers')

# Fallback URL — override via PRICE_SHEET_CSV_URL in settings/.env
DEFAULT_CSV_URL = getattr(settings, 'PRICE_SHEET_CSV_URL', '')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 WorldInflationTracker/1.0',
}

# Base period for WIT CPI — must match CBSL's 2021=100
WIT_BASE_PERIOD = date(2021, 1, 1)


class Command(BaseCommand):
    help = 'Import WIT real-world prices from Google Sheets and recompute WIT CPI'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, help='Google Sheets CSV URL (overrides settings)')
        parser.add_argument('--country', type=str, default='LKA')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be imported without saving')
        parser.add_argument('--recompute-only', action='store_true',
                            help='Skip import, just recompute WIT CPI from existing observations')
        parser.add_argument('--force', action='store_true',
                            help='Overwrite existing price observations')

    def handle(self, *args, **options):
        try:
            country = Country.objects.get(code=options['country'], is_active=True)
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Country {options['country']} not found"))
            return

        if not options.get('recompute_only'):
            csv_url = options.get('url') or DEFAULT_CSV_URL
            if not csv_url:
                self.stderr.write(self.style.ERROR(
                    "No CSV URL provided. Set PRICE_SHEET_CSV_URL in settings "
                    "or pass --url 'https://...'"
                ))
                return

            self.stdout.write(f"Fetching price sheet from Google Sheets...")
            rows = self._fetch_csv(csv_url)
            if rows is None:
                return

            months = self._parse_header(rows[0] if rows else [])
            if not months:
                self.stderr.write(self.style.ERROR(
                    "Could not parse month columns from sheet header. "
                    "Check the sheet format — column headers should be like 'Jan 2021', 'Feb 2021', etc."
                ))
                return

            self.stdout.write(
                f"Found {len(months)} month columns: "
                f"{months[0].strftime('%b %Y')} → {months[-1].strftime('%b %Y')}"
            )

            imported, skipped, failed = self._import_prices(
                rows[1:], months, country, options
            )

            if not options.get('dry_run'):
                self.stdout.write(self.style.SUCCESS(
                    f"Import complete: {imported} prices saved, "
                    f"{skipped} skipped (blank/existing), {failed} failed (item not found)"
                ))

        # Recompute WIT CPI
        if not options.get('dry_run'):
            self.stdout.write("\nRecomputing WIT CPI indices...")
            self._recompute_wit_cpi(country)

    def _fetch_csv(self, url: str):
        """Download and parse CSV from Google Sheets."""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            content = resp.text
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            self.stdout.write(f"  Downloaded {len(rows)} rows.")
            return rows
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch CSV: {e}"))
            return None

    def _parse_header(self, header_row: list) -> list:
        """
        Parse month columns from the header row.
        Columns 0-3 are: Group, Item, Unit, Source/Notes
        Columns 4+ are month labels like 'Jan\n2021' or 'Jan 2021'
        """
        months = []
        for cell in header_row[4:]:
            cell = cell.strip().replace('\n', ' ')
            if not cell:
                continue
            try:
                dt = self._parse_month(cell)
                if dt:
                    months.append(dt)
            except Exception:
                pass
        return months

    def _parse_month(self, text: str) -> date | None:
        """Parse 'Jan 2021', 'Jan\n2021', 'January 2021' into a date."""
        from datetime import datetime
        text = text.strip().replace('\n', ' ')
        for fmt in ['%b %Y', '%B %Y', '%m/%Y', '%Y-%m']:
            try:
                dt = datetime.strptime(text, fmt)
                return date(dt.year, dt.month, 1)
            except ValueError:
                pass
        return None

    def _import_prices(self, data_rows, months, country, options):
        """Load price observations from CSV rows."""
        imported = 0
        skipped = 0
        failed = 0

        for row in data_rows:
            if not row or len(row) < 3:
                continue

            item_name = row[1].strip() if len(row) > 1 else ''
            if not item_name or item_name.startswith('▸') or item_name.startswith('▶'):
                # Group header row — skip
                continue

            # Find matching basket item
            item = BasketItem.objects.filter(
                country=country,
                name__iexact=item_name,
                is_active=True,
            ).first()

            if not item:
                # Try partial match
                item = BasketItem.objects.filter(
                    country=country,
                    name__icontains=item_name[:20],
                    is_active=True,
                ).first()

            if not item:
                if options.get('verbosity', 1) > 1:
                    self.stdout.write(self.style.WARNING(f"  Item not found: {item_name}"))
                failed += 1
                continue

            # Process each month column
            for i, month_date in enumerate(months):
                col_idx = 4 + i
                if col_idx >= len(row):
                    break

                price_str = row[col_idx].strip().replace(',', '')
                if not price_str:
                    skipped += 1
                    continue

                try:
                    price = Decimal(price_str)
                    if price <= 0:
                        skipped += 1
                        continue
                except InvalidOperation:
                    skipped += 1
                    continue

                # Check if observation already exists
                existing = PriceObservation.objects.filter(
                    item=item,
                    country=country,
                    observation_date=month_date,
                ).first()

                if existing and not options.get('force'):
                    skipped += 1
                    continue

                if options.get('dry_run'):
                    self.stdout.write(
                        f"  [DRY RUN] {month_date.strftime('%b %Y')} "
                        f"{item.name}: LKR {price}"
                    )
                    imported += 1
                    continue

                if existing:
                    existing.price = price
                    existing.source_name = 'Google Sheets (WIT Price Sheet)'
                    existing.scrape_method = 'manual'
                    existing.save()
                else:
                    PriceObservation.objects.create(
                        item=item,
                        country=country,
                        observation_date=month_date,
                        price=price,
                        currency_code=country.currency_code,
                        source_url='Google Sheets (WIT Price Sheet)',
                        source_name='WIT Price Sheet',
                        scrape_method='manual',
                        raw_data={'source': 'google_sheets_price_sheet'},
                        is_validated=False,
                    )

                imported += 1

        return imported, skipped, failed

    def _recompute_wit_cpi(self, country):
        """
        Recompute WIT CPI indices for all months that have price data.
        Uses Jan 2021 as the base period to match CBSL's 2021=100 series.
        """
        import subprocess
        from django.conf import settings

        # Find date range of available price observations
        from django.db.models import Min, Max
        agg = PriceObservation.objects.filter(country=country).aggregate(
            min_date=Min('observation_date'),
            max_date=Max('observation_date'),
        )

        if not agg['min_date']:
            self.stdout.write(self.style.WARNING("No price observations found — skipping CPI computation."))
            return

        start = agg['min_date'].strftime('%Y-%m')
        end = agg['max_date'].strftime('%Y-%m')

        self.stdout.write(f"  Computing WIT CPI from {start} to {end}...")

        try:
            result = subprocess.run(
                [
                    'python3', 'manage.py', 'compute_cpi',
                    '--country', country.code,
                    '--start', start,
                    '--end', end,
                    '--force',
                ],
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS("  WIT CPI recomputed successfully."))
                # Show last few lines of output
                for line in result.stdout.strip().split('\n')[-5:]:
                    self.stdout.write(f"    {line}")
            else:
                self.stderr.write(self.style.ERROR(f"  CPI compute failed: {result.stderr}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"  CPI compute error: {e}"))

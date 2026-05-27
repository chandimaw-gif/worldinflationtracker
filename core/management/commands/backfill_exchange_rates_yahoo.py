"""
Backfill historical USD/LKR exchange rates from Yahoo Finance CSV.
No API key required.

Usage:
    python manage.py backfill_exchange_rates_yahoo --years 2
    python manage.py backfill_exchange_rates_yahoo --years 5 --interval 1mo
"""

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal

import requests
from django.core.management.base import BaseCommand

from core.models import Country, ExchangeRate


YAHOO_DOWNLOAD_URL = "https://query1.finance.yahoo.com/v7/finance/download/USDLKR=X"


class Command(BaseCommand):
    help = 'Backfill historical USD/LKR exchange rates from Yahoo Finance (no API key)'

    def add_arguments(self, parser):
        parser.add_argument('--years', type=int, default=2, help='Number of years to backfill')
        parser.add_argument('--interval', type=str, default='1mo', choices=['1d', '1wk', '1mo'],
                            help='Data interval: 1d=daily, 1wk=weekly, 1mo=monthly')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        country = Country.objects.filter(code='LKA', is_active=True).first()
        if not country:
            self.stderr.write(self.style.ERROR("LKA country not found"))
            return

        end_date = date.today()
        start_date = end_date - timedelta(days=options['years'] * 365)

        # Yahoo uses Unix timestamps in seconds
        period1 = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        period2 = int(datetime.combine(end_date, datetime.min.time()).timestamp())
        interval = options['interval']

        url = (
            f"{YAHOO_DOWNLOAD_URL}?"
            f"period1={period1}&period2={period2}"
            f"&interval={interval}&events=history"
        )

        self.stdout.write(f"Fetching USD/LKR from Yahoo Finance ({interval})")
        self.stdout.write(f"Period: {start_date} to {end_date}")

        try:
            resp = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
            }, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Yahoo Finance request failed: {e}"))
            return

        # Parse CSV
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)

        if not rows:
            self.stderr.write(self.style.WARNING("No data returned from Yahoo Finance"))
            return

        created = 0
        skipped = 0

        for row in rows:
            row_date = row.get('Date', '')
            close_price = row.get('Close', '')

            if not row_date or not close_price or close_price == 'null':
                skipped += 1
                continue

            try:
                rate = Decimal(str(close_price))
            except Exception:
                skipped += 1
                continue

            if options['dry_run']:
                self.stdout.write(f"  [DRY RUN] {row_date}: {rate}")
                continue

            ExchangeRate.objects.update_or_create(
                country=country,
                rate_date=row_date,
                base_currency='USD',
                defaults={
                    'local_currency': 'LKR',
                    'rate': rate,
                    'source': f'Yahoo Finance ({interval})',
                }
            )
            created += 1

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f"Dry run complete. Would create/update {len(rows) - skipped} records."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done. Created/updated: {created}, Skipped: {skipped}"
            ))

"""
Backfill historical USD/LKR exchange rates from FRED (St. Louis Fed) API.

Usage:
    python manage.py backfill_exchange_rates --years 5
    python manage.py backfill_exchange_rates --start 2020-01-01 --end 2024-12-31

Requires FRED_API_KEY environment variable or setting.
Free API key: https://fred.stlouisfed.org/docs/api/api_key.html
"""

import os
import requests
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.conf import settings

from core.models import Country, ExchangeRate


FRED_SERIES_ID = 'DEXSLUS'  # Sri Lankan Rupees to U.S. Dollar Spot Exchange Rate
FRED_API_URL = 'https://api.stlouisfed.org/fred/series/observations'


class Command(BaseCommand):
    help = 'Backfill historical USD/LKR exchange rates from FRED API'

    def add_arguments(self, parser):
        parser.add_argument('--years', type=int, help='Number of years to backfill')
        parser.add_argument('--start', type=str, help='Start date YYYY-MM-DD')
        parser.add_argument('--end', type=str, help='End date YYYY-MM-DD')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        country = Country.objects.filter(code='LKA', is_active=True).first()
        if not country:
            self.stderr.write(self.style.ERROR("LKA country not found"))
            return

        api_key = os.environ.get('FRED_API_KEY', getattr(settings, 'FRED_API_KEY', None))
        if not api_key:
            self.stderr.write(self.style.ERROR(
                "FRED_API_KEY not set. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html\n"
                "Then set it as environment variable: export FRED_API_KEY=your_key"
            ))
            return

        end_date = date.today()
        if options['end']:
            end_date = date.fromisoformat(options['end'])

        if options['start']:
            start_date = date.fromisoformat(options['start'])
        elif options['years']:
            start_date = end_date - timedelta(days=options['years'] * 365)
        else:
            start_date = end_date - timedelta(days=365 * 2)  # default 2 years

        self.stdout.write(f"Fetching USD/LKR rates from {start_date} to {end_date}")

        params = {
            'series_id': FRED_SERIES_ID,
            'api_key': api_key,
            'file_type': 'json',
            'observation_start': start_date.isoformat(),
            'observation_end': end_date.isoformat(),
        }

        try:
            resp = requests.get(FRED_API_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"FRED API request failed: {e}"))
            return

        observations = data.get('observations', [])
        if not observations:
            self.stderr.write(self.style.WARNING("No observations returned from FRED"))
            return

        created = 0
        skipped = 0

        for obs in observations:
            obs_date = obs.get('date')
            value = obs.get('value', '.')

            if not obs_date or value == '.':
                skipped += 1
                continue

            try:
                rate = Decimal(str(value))
            except Exception:
                skipped += 1
                continue

            if options['dry_run']:
                self.stdout.write(f"  [DRY RUN] {obs_date}: {rate}")
                continue

            ExchangeRate.objects.update_or_create(
                country=country,
                rate_date=obs_date,
                base_currency='USD',
                defaults={
                    'local_currency': 'LKR',
                    'rate': rate,
                    'source': 'FRED/St. Louis Fed',
                }
            )
            created += 1

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f"Dry run complete. Would create/update {len(observations) - skipped} records."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. Created/updated: {created}, Skipped (no data): {skipped}"))

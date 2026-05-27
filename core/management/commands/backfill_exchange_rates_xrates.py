import os
import re
import time
from datetime import date, timedelta

import requests
from django.core.management.base import BaseCommand

from core.models import Country, ExchangeRate


class Command(BaseCommand):
    help = "Backfill USD/LKR exchange rates from x-rates.com (no API key required)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--years",
            type=int,
            default=2,
            help="Number of years of historical data to fetch (default: 2)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fetched without saving",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing records",
        )

    def handle(self, *args, **options):
        years = options["years"]
        dry_run = options["dry_run"]
        force = options["force"]

        country, _ = Country.objects.get_or_create(
            code="LKA",
            defaults={
                "name": "Sri Lanka",
                "currency_code": "LKR",
                "currency_name": "Sri Lankan Rupee",
            },
        )

        end_date = date.today()
        start_date = end_date.replace(year=end_date.year - years)
        if start_date.month == 2 and start_date.day == 29:
            start_date = start_date.replace(day=28)

        self.stdout.write(
            self.style.NOTICE(
                f"Fetching USD/LKR rates from {start_date} to {end_date} ({years} years)"
            )
        )

        # Build list of monthly dates (1st of each month)
        dates_to_fetch = []
        current = date(start_date.year, start_date.month, 1)
        while current <= end_date:
            dates_to_fetch.append(current)
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        self.stdout.write(f"Total dates to fetch: {len(dates_to_fetch)}")

        # Check existing
        existing_dates = set(
            ExchangeRate.objects.filter(
                country=country, base_currency="USD", local_currency="LKR"
            ).values_list("rate_date", flat=True)
        )

        created = 0
        updated = 0
        failed = 0
        skipped = 0

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.5",
            }
        )

        for fetch_date in dates_to_fetch:
            if fetch_date in existing_dates and not force:
                skipped += 1
                self.stdout.write(f"  {fetch_date}: SKIP (exists)")
                continue

            url = (
                f"https://www.x-rates.com/historical/"
                f"?from=USD&amount=1&date={fetch_date}"
            )

            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f"  {fetch_date}: REQUEST FAILED - {e}")
                )
                time.sleep(2)
                continue

            # Extract LKR rate
            match = re.search(
                r"Sri Lankan Rupee</td>\s*<td[^>]*><a[^>]*>([0-9]+\.[0-9]+)</a>",
                resp.text,
            )
            if not match:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f"  {fetch_date}: RATE NOT FOUND in HTML")
                )
                time.sleep(2)
                continue

            rate_value = match.group(1)

            if dry_run:
                self.stdout.write(f"  {fetch_date}: {rate_value} (dry-run)")
            else:
                if fetch_date in existing_dates and force:
                    ExchangeRate.objects.filter(
                        country=country,
                        base_currency="USD",
                        target_currency="LKR",
                        rate_date=fetch_date,
                    ).update(
                        rate=rate_value,
                        source="x-rates.com",
                    )
                    updated += 1
                    self.stdout.write(f"  {fetch_date}: {rate_value} (updated)")
                else:
                    ExchangeRate.objects.create(
                        country=country,
                        base_currency="USD",
                        target_currency="LKR",
                        rate=rate_value,
                        rate_date=fetch_date,
                        source="x-rates.com",
                    )
                    created += 1
                    self.stdout.write(f"  {fetch_date}: {rate_value} (created)")

            # Polite delay
            time.sleep(1.5)

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created}, Updated: {updated}, "
                f"Skipped: {skipped}, Failed: {failed}"
            )
        )

import re
from datetime import date

import requests
from django.core.management.base import BaseCommand

from core.models import Country, ExchangeRate


class Command(BaseCommand):
    help = (
        "Fetch current USD/LKR exchange rate from x-rates.com "
        "and store it if not already present for today"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fetched without saving",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite today's record if it exists",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        today = date.today()

        country, _ = Country.objects.get_or_create(
            code="LKA",
            defaults={
                "name": "Sri Lanka",
                "currency_code": "LKR",
                "currency_name": "Sri Lankan Rupee",
            },
        )

        # Skip if already exists (unless force)
        if not force:
            existing = ExchangeRate.objects.filter(
                country=country,
                base_currency="USD",
                local_currency="LKR",
                rate_date=today,
            ).first()
            if existing:
                self.stdout.write(
                    self.style.WARNING(
                        f"Rate for {today} already exists: {existing.rate}. "
                        f"Use --force to overwrite."
                    )
                )
                return

        url = (
            f"https://www.x-rates.com/historical/"
            f"?from=USD&amount=1&date={today}"
        )

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

        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Request failed: {e}")
            )
            return

        match = re.search(
            r"Sri Lankan Rupee</td>\s*<td[^>]*><a[^>]*>([0-9]+\.[0-9]+)</a>",
            resp.text,
        )
        if not match:
            self.stdout.write(
                self.style.ERROR("Rate not found in HTML response")
            )
            return

        rate_value = match.group(1)

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(f"{today}: {rate_value} (dry-run)")
            )
            return

        if force:
            ExchangeRate.objects.update_or_create(
                country=country,
                base_currency="USD",
                local_currency="LKR",
                rate_date=today,
                defaults={"rate": rate_value, "source": "x-rates.com"},
            )
            self.stdout.write(
                self.style.SUCCESS(f"{today}: {rate_value} (updated/created)")
            )
        else:
            ExchangeRate.objects.create(
                country=country,
                base_currency="USD",
                local_currency="LKR",
                rate=rate_value,
                rate_date=today,
                source="x-rates.com",
            )
            self.stdout.write(
                self.style.SUCCESS(f"{today}: {rate_value} (created)")
            )

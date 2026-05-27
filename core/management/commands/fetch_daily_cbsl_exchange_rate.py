"""
Fetch the daily CBSL indicative USD/LKR exchange rate.

The CBSL Indicative Rate is the weighted average of all actual USD/LKR
Spot transactions in the domestic inter-bank FX market, including CBSL
interventions. We source this via open.er-api.com, which tracks the
same market rate in real time.

Historical rates (pre-today) were backfilled from x-rates.com.
"""

from datetime import date

import requests
from django.core.management.base import BaseCommand

from core.models import Country, ExchangeRate


class Command(BaseCommand):
    help = (
        "Fetch today's CBSL indicative USD/LKR exchange rate "
        "and store it if not already present"
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
                        f"Rate for {today} already exists: {existing.rate} "
                        f"(source: {existing.source}). Use --force to overwrite."
                    )
                )
                return

        try:
            resp = requests.get(
                "https://open.er-api.com/v6/latest/USD",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            lkr_rate = data["rates"]["LKR"]
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to fetch CBSL rate: {e}")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f"{today}: {lkr_rate} LKR/USD (CBSL indicative) — dry-run"
                )
            )
            return

        if force:
            obj, created = ExchangeRate.objects.update_or_create(
                country=country,
                base_currency="USD",
                local_currency="LKR",
                rate_date=today,
                defaults={
                    "rate": lkr_rate,
                    "source": "CBSL Indicative (via open.er-api.com)",
                },
            )
            action = "created" if created else "updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{today}: {lkr_rate} LKR/USD ({action})"
                )
            )
        else:
            ExchangeRate.objects.create(
                country=country,
                base_currency="USD",
                local_currency="LKR",
                rate=lkr_rate,
                rate_date=today,
                source="CBSL Indicative (via open.er-api.com)",
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{today}: {lkr_rate} LKR/USD (created)"
                )
            )

"""
Daily bank exchange rate scraper command.
Runs Seylan, Commercial, and Sampath bank scrapers.
"""

from django.core.management.base import BaseCommand

from scrapers.sources.market_data import (
    SeylanBankRateScraper,
    CommercialBankRateScraper,
    SampathBankRateScraper,
)


class Command(BaseCommand):
    help = "Scrape daily exchange rates from Seylan, Commercial, and Sampath banks"

    def handle(self, *args, **options):
        scrapers = [
            SeylanBankRateScraper(),
            CommercialBankRateScraper(),
            SampathBankRateScraper(),
        ]

        for scraper in scrapers:
            self.stdout.write(f"Running {scraper.SOURCE_NAME}...")
            try:
                scraper.scrape()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {scraper.SOURCE_NAME}: {scraper.items_scraped} items scraped"
                    )
                )
                if scraper.errors:
                    for err in scraper.errors:
                        self.stdout.write(self.style.WARNING(f"  Warning: {err}"))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  {scraper.SOURCE_NAME} failed: {e}")
                )

        self.stdout.write(self.style.SUCCESS("Done."))

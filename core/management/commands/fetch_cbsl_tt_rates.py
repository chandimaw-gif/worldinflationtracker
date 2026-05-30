"""
Management command: fetch_cbsl_tt_rates

Fetches the daily average TT buying/selling exchange rates published by CBSL.
These represent the average of quotes from licensed commercial banks at 9:30 AM.

Usage:
    python3 manage.py fetch_cbsl_tt_rates
    python3 manage.py fetch_cbsl_tt_rates --dry-run
"""

from django.core.management.base import BaseCommand
from scrapers.sources.cbsl_tt_rates import run_cbsl_tt_scraper, fetch_cbsl_tt_rates


class Command(BaseCommand):
    help = 'Fetch CBSL daily average TT buying/selling exchange rates'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Show rates without saving')

    def handle(self, *args, **options):
        if options.get('dry_run'):
            self.stdout.write("Fetching CBSL TT rates (dry run)...")
            rates = fetch_cbsl_tt_rates()
            if not rates:
                self.stdout.write(self.style.WARNING("No rates found."))
                return
            for r in rates:
                self.stdout.write(
                    f"  {r['currency']}: Buy={r.get('buying')} Sell={r.get('selling')} ({r['date']})"
                )
            return

        self.stdout.write("Fetching CBSL TT rates...")
        result = run_cbsl_tt_scraper()

        if result['status'] == 'success':
            self.stdout.write(self.style.SUCCESS(
                f"Saved {result['items_scraped']} rates: {', '.join(result.get('currencies', []))}"
            ))
        else:
            self.stdout.write(self.style.ERROR(f"Failed: {result.get('error')}"))

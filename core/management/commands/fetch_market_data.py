"""
Run market data scrapers manually.

Usage:
    python manage.py fetch_market_data --all
    python manage.py fetch_market_data --source cbsl_market
    python manage.py fetch_market_data --source seylan
"""

from django.core.management.base import BaseCommand

from scrapers.sources.market_data import (
    CBSLMarketRateScraper,
    SeylanBankRateScraper,
    CommercialBankRateScraper,
    SampathBankRateScraper,
)


SCRAPER_MAP = {
    'cbsl_market': CBSLMarketRateScraper,
    'seylan': SeylanBankRateScraper,
    'commercial': CommercialBankRateScraper,
    'sampath': SampathBankRateScraper,
}


class Command(BaseCommand):
    help = 'Run market data scrapers'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Run all market scrapers')
        parser.add_argument('--source', type=str, help=f'Specific source. Options: {", ".join(SCRAPER_MAP.keys())}')
        parser.add_argument('--list', action='store_true', help='List available scrapers')

    def handle(self, *args, **options):
        if options['list']:
            self.stdout.write(self.style.SUCCESS('Available market scrapers:'))
            for name in sorted(SCRAPER_MAP.keys()):
                self.stdout.write(f'  - {name}')
            return

        if options['all']:
            scrapers = list(SCRAPER_MAP.values())
        elif options['source']:
            source = options['source'].lower()
            if source not in SCRAPER_MAP:
                self.stderr.write(self.style.ERROR(f'Unknown source: {source}'))
                self.stderr.write(f'Available: {", ".join(SCRAPER_MAP.keys())}')
                return
            scrapers = [SCRAPER_MAP[source]]
        else:
            self.stderr.write(self.style.ERROR('Please provide --all, --source, or --list'))
            return

        total_scraped = 0
        total_failed = 0

        for scraper_class in scrapers:
            self.stdout.write(self.style.NOTICE(f'\nRunning {scraper_class.__name__}...'))
            try:
                scraper = scraper_class()
                result = scraper.run()

                status_color = self.style.SUCCESS if result['status'] == 'success' else (
                    self.style.WARNING if result['status'] == 'partial' else self.style.ERROR
                )
                self.stdout.write(status_color(
                    f"  Status: {result['status']} | Scraped: {result['items_scraped']} | Failed: {result['items_failed']}"
                ))

                if result.get('errors'):
                    for error in result['errors']:
                        self.stdout.write(self.style.WARNING(f'  Error: {error}'))

                total_scraped += result['items_scraped']
                total_failed += result['items_failed']

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Fatal error: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n---\nTotal market data: {total_scraped} scraped, {total_failed} failed'
        ))

"""
Management command to run scrapers manually.

Usage:
    python manage.py run_scrapers --all
    python manage.py run_scrapers --source ceypetco
    python manage.py run_scrapers --source keells
    python manage.py run_scrapers --source cbsl
"""

from django.core.management.base import BaseCommand

from scrapers.sources.cbsl import CBSLExchangeRateScraper, CBSLGoldScraper
from scrapers.sources.ceypetco import CEYPETCOScraper
from scrapers.sources.utilities import (
    CEBTariffScraper, LitroGasScraper, LaugfsGasScraper,
    DialogScraper, SLTScraper
)
from scrapers.sources.keells import KeellsScraper
from scrapers.sources.spar import SparScraper
from scrapers.sources.singer import SingerScraper


SCRAPER_MAP = {
    'cbsl': CBSLExchangeRateScraper,
    'cbsl_gold': CBSLGoldScraper,
    'ceypetco': CEYPETCOScraper,
    'ceb': CEBTariffScraper,
    'litro': LitroGasScraper,
    'laugfs': LaugfsGasScraper,
    'dialog': DialogScraper,
    'slt': SLTScraper,
    'keells': KeellsScraper,
    'spar': SparScraper,
    'singer': SingerScraper,
}


class Command(BaseCommand):
    help = 'Run price scrapers manually'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Run all scrapers')
        parser.add_argument('--source', type=str, help=f'Run specific source. Options: {", ".join(SCRAPER_MAP.keys())}')
        parser.add_argument('--list', action='store_true', help='List available scrapers')

    def handle(self, *args, **options):
        if options['list']:
            self.stdout.write(self.style.SUCCESS('Available scrapers:'))
            for name in sorted(SCRAPER_MAP.keys()):
                self.stdout.write(f'  - {name}')
            return

        if options['all']:
            scrapers = list(SCRAPER_MAP.values())
        elif options['source']:
            source = options['source'].lower()
            if source not in SCRAPER_MAP:
                self.stdout.write(self.style.ERROR(f'Unknown source: {source}'))
                self.stdout.write(f'Available: {", ".join(SCRAPER_MAP.keys())}')
                return
            scrapers = [SCRAPER_MAP[source]]
        else:
            self.stdout.write(self.style.ERROR('Please provide --all, --source, or --list'))
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
                    f"  Status: {result['status']} | "
                    f"Scraped: {result['items_scraped']} | "
                    f"Failed: {result['items_failed']}"
                ))

                if result['errors']:
                    for error in result['errors']:
                        self.stdout.write(self.style.WARNING(f'  Error: {error}'))

                total_scraped += result['items_scraped']
                total_failed += result['items_failed']

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Fatal error: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n---\nTotal: {total_scraped} scraped, {total_failed} failed'
        ))

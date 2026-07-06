"""
Management command: fetch_news_now

Manually trigger an immediate news fetch from all RSS sources.
Useful for initial population and testing.

Usage:
    python3 manage.py fetch_news_now
    python3 manage.py fetch_news_now --limit 5
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Immediately fetch news from all RSS sources'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10,
                            help='Max articles per source (default 10)')

    def handle(self, *args, **options):
        self.stdout.write("Fetching news from all sources...")
        try:
            from scrapers.tasks import fetch_news_feeds
            result = fetch_news_feeds()
            self.stdout.write(self.style.SUCCESS(str(result)))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed: {e}"))

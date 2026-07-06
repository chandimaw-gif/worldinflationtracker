import csv
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from core.models import NewsArticle

NEWS_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSE_6nH-_hbGILUwWNJ3R89MWgSRAwSPU0eYlABobvV8VvR2qbkiUVxCXoImuGHx29J_dIpRH3InXnb/pub?gid=845580084&single=true&output=csv"


class Command(BaseCommand):
    help = 'Import curated news from Google Sheet News tab'

    def handle(self, *args, **options):
        self.stdout.write("Fetching news from Google Sheet...")
        try:
            response = requests.get(NEWS_SHEET_URL, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch sheet: {e}"))
            return

        content = response.content.decode('utf-8-sig')
        lines = content.strip().split('\n')

        created = 0
        skipped = 0

        for line in lines[1:]:  # Skip header
            line = line.strip()
            if not line:
                continue

            # Handle tab-separated data inside quoted fields
            if line.startswith('"') and line.endswith('"') and '\t' in line:
                parts = line[1:-1].split('\t')
            else:
                parts = list(csv.reader([line]))[0]

            if len(parts) < 5:
                continue

            date_str = parts[0].strip()
            source = parts[1].strip()
            headline = parts[2].strip()
            synopsis = parts[3].strip()
            link = parts[4].strip()

            if not headline or not link:
                continue

            # Parse date
            try:
                published = datetime.strptime(date_str, '%d/%m/%Y').date()
            except ValueError:
                try:
                    published = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    self.stdout.write(self.style.WARNING(f"Skipping bad date: {date_str}"))
                    continue

            # Create or update
            _, was_created = NewsArticle.objects.update_or_create(
                source_url=link,
                defaults={
                    'title': headline,
                    'summary': synopsis,
                    'source_name': source,
                    'published_at': datetime.combine(published, datetime.min.time()),
                    'category': 'economy',
                }
            )

            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"News import complete. Created: {created}, Updated/Skipped: {skipped}"
        ))

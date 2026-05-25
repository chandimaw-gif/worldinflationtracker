"""
Download and parse CBSL Daily Price Report PDF.

Usage:
    python manage.py download_cbsl_report
    python manage.py download_cbsl_report --date 2026-05-22
    python manage.py download_cbsl_report --historical --months 12
"""

import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Download CBSL Daily Price Report PDF'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='Specific date (YYYY-MM-DD)')
        parser.add_argument('--historical', action='store_true', help='Download historical reports')
        parser.add_argument('--months', type=int, default=12, help='How many months back for historical')
        parser.add_argument('--output-dir', type=str, default='data/cbsl_reports', help='Output directory')

    def handle(self, *args, **options):
        output_dir = os.path.join(settings.BASE_DIR, options['output_dir'])
        os.makedirs(output_dir, exist_ok=True)

        if options['historical']:
            self.download_historical(output_dir, options['months'])
        elif options['date']:
            date_obj = datetime.strptime(options['date'], '%Y-%m-%d').date()
            self.download_single(date_obj, output_dir)
        else:
            self.download_single(datetime.now().date(), output_dir)

    def download_single(self, date_obj, output_dir):
        """Download a single day's report."""
        date_str = date_obj.strftime('%Y%m%d')

        # CBSL uses multiple filename patterns
        patterns = [
            f'price_report_{date_str}_e_0.pdf',
            f'price_report_{date_str}_e.pdf',
        ]

        base_url = 'https://www.cbsl.gov.lk/sites/default/files/cbslweb_documents/statistics/pricerpt/'

        for filename in patterns:
            url = urljoin(base_url, filename)
            self.stdout.write(f"Trying: {url}")
            try:
                resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
                if resp.status_code == 200 and resp.headers.get('content-type', '').startswith('application/pdf'):
                    output_path = os.path.join(output_dir, filename)
                    with open(output_path, 'wb') as f:
                        f.write(resp.content)
                    self.stdout.write(self.style.SUCCESS(f"Downloaded: {output_path} ({len(resp.content)} bytes)"))
                    return output_path
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed: {e}"))
                continue

        self.stdout.write(self.style.ERROR(f"Could not find report for {date_obj}"))
        return None

    def download_historical(self, output_dir, months):
        """Download 1 report per month going back."""
        today = datetime.now().date()
        downloaded = 0
        failed = 0

        for i in range(months):
            # Target the 15th of each month (most likely to have a report)
            target_date = today - timedelta(days=i * 30)
            target_date = target_date.replace(day=15)

            result = self.download_single(target_date, output_dir)
            if result:
                downloaded += 1
            else:
                failed += 1

        self.stdout.write(self.style.SUCCESS(f'\nDownloaded: {downloaded}, Failed: {failed}'))

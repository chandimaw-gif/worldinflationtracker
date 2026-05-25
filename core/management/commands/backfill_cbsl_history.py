"""
Backfill historical prices from CBSL Daily Price Report PDFs.

Downloads 1 report per month going back N years, parses each PDF,
and enters prices into the database with the correct observation_date.

Usage:
    python manage.py backfill_cbsl_history --years 3
    python manage.py backfill_cbsl_history --years 1 --dry-run
    python manage.py backfill_cbsl_history --years 2 --start-year 2024
"""

import os
import re
from datetime import datetime, date
from decimal import Decimal
from calendar import monthrange

import requests
from django.conf import settings
from django.core.management.base import BaseCommand


CBSL_TO_BASKET = {
    'Coconut oil': 'Coconut Oil',
    'Red Dhal': 'Dhal (Mysoor/Red Lentils)',
    'Sugar (White)': 'Sugar — White granulated',
    'Egg (White)': 'Eggs — Fresh hen',
}


class Command(BaseCommand):
    help = 'Backfill historical prices from CBSL Daily Price Reports'

    def add_arguments(self, parser):
        parser.add_argument('--years', type=int, default=2, help='How many years back to go')
        parser.add_argument('--start-year', type=int, help='Start from a specific year')
        parser.add_argument('--dry-run', action='store_true', help='Download and parse but do not save to DB')
        parser.add_argument('--report-dir', type=str, default='data/cbsl_reports', help='Report directory')

    def handle(self, *args, **options):
        from pypdf import PdfReader
        from core.models import BasketItem, PriceObservation

        report_dir = os.path.join(settings.BASE_DIR, options['report_dir'])
        os.makedirs(report_dir, exist_ok=True)

        end_year = options['start_year'] or datetime.now().year
        start_year = end_year - options['years']

        self.stdout.write(self.style.NOTICE(f"Backfilling from {start_year} to {end_year} (1 report per month)"))

        total_downloaded = 0
        total_parsed = 0
        total_entered = 0

        for year in range(end_year, start_year - 1, -1):
            for month in range(12, 0, -1):
                # Skip future months in current year
                if year == datetime.now().year and month > datetime.now().month:
                    continue

                # Target the 15th of each month (most likely to have a report)
                target_day = min(15, monthrange(year, month)[1])
                target_date = date(year, month, target_day)

                pdf_path = self._download_report(target_date, report_dir)
                if not pdf_path:
                    self.stdout.write(self.style.WARNING(f"  No report for {target_date}"))
                    continue

                total_downloaded += 1
                prices = self._parse_pdf(pdf_path)

                if not prices:
                    self.stdout.write(self.style.WARNING(f"  Could not parse {target_date}"))
                    continue

                total_parsed += 1

                if options['dry_run']:
                    self.stdout.write(f"  {target_date}: {len(prices)} prices found (dry run)")
                    continue

                entered = self._save_prices(target_date, prices)
                total_entered += entered
                self.stdout.write(self.style.SUCCESS(f"  {target_date}: {entered} prices entered"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Downloaded: {total_downloaded}, Parsed: {total_parsed}, Entered: {total_entered}"
        ))

    def _download_report(self, target_date, report_dir):
        """Download a single report, trying multiple filename patterns."""
        date_str = target_date.strftime('%Y%m%d')
        patterns = [
            f'price_report_{date_str}_e_0.pdf',
            f'price_report_{date_str}_e.pdf',
        ]
        base_url = 'https://www.cbsl.gov.lk/sites/default/files/cbslweb_documents/statistics/pricerpt/'

        for filename in patterns:
            url = base_url + filename
            try:
                resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    output_path = os.path.join(report_dir, filename)
                    with open(output_path, 'wb') as f:
                        f.write(resp.content)
                    return output_path
            except Exception:
                continue
        return None

    def _parse_pdf(self, pdf_path):
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            all_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return {}

        prices = {}

        for cbsl_name, basket_name in CBSL_TO_BASKET.items():
            price = self._find_wholesale_price(all_text, cbsl_name)
            if price:
                prices[basket_name] = price

        rice_prices = self._extract_rice_prices(all_text)
        prices.update(rice_prices)

        return prices

    def _find_wholesale_price(self, text, item_name):
        lines = text.split('\n')
        for line in lines:
            if item_name in line:
                values = re.findall(r'[\d,]+\.\d{2}', line)
                if len(values) >= 2:
                    try:
                        price = Decimal(values[1].replace(',', ''))
                        if price > 0:
                            return price
                    except Exception:
                        pass
        return None

    def _extract_rice_prices(self, text):
        prices = {}
        samba_match = re.search(r'Samba\s+Rs\.\/kg\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', text)
        if samba_match:
            try:
                price = Decimal(samba_match.group(2).replace(',', ''))
                if price > 100:
                    prices['Rice — Samba'] = price
            except Exception:
                pass

        nadu_match = re.search(r'Nadu\s+Rs\.\/kg\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})', text)
        if nadu_match:
            try:
                price = Decimal(nadu_match.group(2).replace(',', ''))
                if price > 100:
                    prices['Rice — Nadu (white, raw)'] = price
            except Exception:
                pass
        return prices

    def _save_prices(self, target_date, prices):
        from core.models import BasketItem, PriceObservation
        entered = 0

        for item_name, price in prices.items():
            item = BasketItem.objects.filter(
                country__code='LKA',
                name=item_name,
                is_active=True,
            ).first()

            if not item:
                continue

            PriceObservation.objects.update_or_create(
                item=item,
                country=item.country,
                observation_date=target_date,
                defaults={
                    'price': price,
                    'currency_code': 'LKR',
                    'source_url': 'https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report',
                    'source_name': 'CBSL Daily Price Report (Historical)',
                    'scrape_method': 'manual',
                    'raw_data': {'source': 'cbsl_pdf_historical', 'report_date': str(target_date)},
                }
            )
            entered += 1

        return entered

"""
Parse CBSL Daily Price Report PDF and extract prices for basket items.

Usage:
    python manage.py parse_cbsl_pdf data/cbsl_reports/price_report_20260522_e_0.pdf
    python manage.py parse_cbsl_pdf --latest
    python manage.py parse_cbsl_pdf --latest --enter
"""

import os
import re
from decimal import Decimal
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand


# Mapping of CBSL item names to our basket item names
CBSL_TO_BASKET = {
    'Coconut oil': 'Coconut Oil',
    'Red Dhal': 'Dhal (Mysoor/Red Lentils)',
    'Sugar (White)': 'Sugar — White granulated',
    'Egg (White)': 'Eggs — Fresh hen',
}


class Command(BaseCommand):
    help = 'Parse CBSL Daily Price Report PDF'

    def add_arguments(self, parser):
        parser.add_argument('pdf_path', nargs='?', help='Path to PDF file')
        parser.add_argument('--latest', action='store_true', help='Parse the latest downloaded PDF')
        parser.add_argument('--enter', action='store_true', help='Auto-enter prices into database')
        parser.add_argument('--report-dir', type=str, default='data/cbsl_reports', help='Report directory')

    def handle(self, *args, **options):
        pdf_path = options.get('pdf_path')

        if options['latest'] or not pdf_path:
            pdf_path = self._find_latest_pdf(options['report_dir'])
            if not pdf_path:
                self.stdout.write(self.style.ERROR("No PDF found. Run: python manage.py download_cbsl_report"))
                return

        if not os.path.exists(pdf_path):
            self.stdout.write(self.style.ERROR(f"PDF not found: {pdf_path}"))
            return

        self.stdout.write(self.style.NOTICE(f"Parsing: {pdf_path}"))
        prices = self._extract_prices(pdf_path)

        if not prices:
            self.stdout.write(self.style.WARNING("No prices extracted from PDF."))
            return

        self._display_prices(prices)

        if options['enter']:
            self._enter_prices(prices)

    def _find_latest_pdf(self, report_dir):
        full_dir = os.path.join(settings.BASE_DIR, report_dir)
        if not os.path.exists(full_dir):
            return None
        pdfs = [f for f in os.listdir(full_dir) if f.endswith('.pdf')]
        if not pdfs:
            return None
        pdfs.sort(key=lambda f: os.path.getmtime(os.path.join(full_dir, f)), reverse=True)
        return os.path.join(full_dir, pdfs[0])

    def _extract_prices(self, pdf_path):
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            all_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"PDF parsing failed: {e}"))
            return {}

        prices = {}

        # Extract report date
        date_match = re.search(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', all_text)
        if date_match:
            prices['_report_date'] = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}"

        # Extract wholesale prices (first "Today" price for each item)
        for cbsl_name, basket_name in CBSL_TO_BASKET.items():
            price = self._find_wholesale_price(all_text, cbsl_name)
            if price:
                prices[basket_name] = price

        # Extract rice prices
        rice_prices = self._extract_rice_prices(all_text)
        prices.update(rice_prices)

        return prices

    def _find_wholesale_price(self, text, item_name):
        """
        Find the first 'Today' price for an item in the wholesale section.
        Format: ItemName Rs./Unit Yesterday Today Yesterday Today ...
        We take the first 'Today' value (second numeric value).
        """
        lines = text.split('\n')
        for line in lines:
            if item_name in line:
                # Extract all numeric values from the line
                values = re.findall(r'[\d,]+\.\d{2}', line)
                if len(values) >= 2:
                    # The pattern is: Yesterday1 Today1 Yesterday2 Today2 ...
                    # Index 1 is the first "Today" price
                    try:
                        price = Decimal(values[1].replace(',', ''))
                        if price > 0:
                            return price
                    except Exception:
                        pass
        return None

    def _extract_rice_prices(self, text):
        """Extract Samba and Nadu rice prices from retail section."""
        prices = {}

        # Look for rice price lines in retail section
        # Format: Samba Rs./kg 245.00 245.00 242.00 ...
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

    def _display_prices(self, prices):
        report_date = prices.pop('_report_date', 'Unknown')
        self.stdout.write(self.style.SUCCESS(f"\nCBSL Daily Price Report - {report_date}\n"))
        self.stdout.write("=" * 55)
        self.stdout.write(f"{'Item':<40} {'Price (LKR)':>14}")
        self.stdout.write("-" * 55)

        for item, price in sorted(prices.items()):
            self.stdout.write(f"{item:<40} {price:>14.2f}")

        self.stdout.write("=" * 55)
        self.stdout.write(f"\nTo enter these prices, run:\n")
        for item, price in sorted(prices.items()):
            self.stdout.write(f'  python manage.py enter_prices --item "{item}" --price {price}')

    def _enter_prices(self, prices):
        from core.models import BasketItem, PriceObservation

        today = datetime.now().date()
        entered = 0

        for item_name, price in prices.items():
            if item_name.startswith('_'):
                continue

            item = BasketItem.objects.filter(
                country__code='LKA',
                name=item_name,
                is_active=True,
            ).first()

            if not item:
                self.stdout.write(self.style.WARNING(f"Basket item not found: {item_name}"))
                continue

            PriceObservation.objects.update_or_create(
                item=item,
                country=item.country,
                observation_date=today,
                defaults={
                    'price': price,
                    'currency_code': 'LKR',
                    'source_url': 'https://www.cbsl.gov.lk/en/statistics/economic-indicators/price-report',
                    'source_name': 'CBSL Daily Price Report',
                    'scrape_method': 'manual',
                    'raw_data': {'source': 'cbsl_pdf'},
                }
            )
            entered += 1
            self.stdout.write(self.style.SUCCESS(f"Entered: {item_name} @ {price}"))

        self.stdout.write(self.style.SUCCESS(f"\nTotal entered: {entered}"))

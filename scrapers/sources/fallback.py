"""
Fallback / manual entry scraper.

When automated scraping fails (e.g., due to bot protection, JS requirements,
or site changes), this module provides:
1. A management command to enter prices manually
2. A scraper that loads manually-entered prices from a JSON file
3. Helpers to mark items as requiring manual entry
"""

import json
import os
from decimal import Decimal
from datetime import date
from typing import Optional

from scrapers.base import BaseScraper


class ManualEntryScraper(BaseScraper):
    """
    Load prices from a manual entry JSON file.

    Expected JSON format (manual_prices.json):
    {
        "2024-05-20": {
            "Rice — Nadu (white, raw)": 185.00,
            "Rice — Samba": 210.00,
            ...
        }
    }
    """

    SOURCE_NAME = "Manual_Entry"
    BASE_URL = ""
    RATE_LIMIT_SECONDS = 0

    def __init__(self, json_path: Optional[str] = None):
        super().__init__()
        self.json_path = json_path or os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'manual_prices.json'
        )

    def scrape(self):
        from core.models import BasketItem

        if not os.path.exists(self.json_path):
            self.log_error(f"Manual prices file not found: {self.json_path}")
            self.items_failed += 1
            return

        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.log_error(f"Invalid JSON in manual prices file: {e}")
            self.items_failed += 1
            return

        today_str = str(date.today())
        today_prices = data.get(today_str, {})

        if not today_prices:
            self.log_error(f"No manual prices found for {today_str}")
            self.items_failed += 1
            return

        for item_name, price_value in today_prices.items():
            item = BasketItem.objects.filter(
                country__code=self.COUNTRY_CODE,
                name=item_name,
                is_active=True,
            ).first()

            if not item:
                # Try partial match
                item = BasketItem.objects.filter(
                    country__code=self.COUNTRY_CODE,
                    name__icontains=item_name,
                    is_active=True,
                ).first()

            if not item:
                self.log_error(f"Basket item not found for manual entry: {item_name}")
                self.items_failed += 1
                continue

            try:
                price = Decimal(str(price_value))
            except Exception as e:
                self.log_error(f"Invalid price for {item_name}: {price_value} ({e})")
                self.items_failed += 1
                continue

            self.save_price(
                item=item,
                price=price,
                observation_date=date.today(),
                source_url='',
                source_name='Manual Entry',
                scrape_method='manual',
                raw_data={'entry_method': 'json_file'},
            )


def create_manual_prices_template():
    """Create a template manual_prices.json file with all basket items."""
    import django
    django.setup()
    from core.models import BasketItem

    items = BasketItem.objects.filter(
        country__code='LKA',
        is_active=True,
    ).order_by('group', 'name')

    template = {}
    for item in items:
        today_str = str(date.today())
        if today_str not in template:
            template[today_str] = {}
        template[today_str][item.name] = None

    output_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'data', 'manual_prices_template.json'
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    print(f"Template created at: {output_path}")
    return output_path

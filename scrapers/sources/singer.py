"""
Singer Sri Lanka scraper.

Target: https://singersl.com
Singer sells electronics, appliances, and home goods.

Items to scrape:
- Paint — Emulsion (Multilac/Nippon)
- Refrigerator — Inverter 250L
- Washing Machine — 7kg Front Load
- Smartphone — Samsung Galaxy A-series
- Television — 43" Smart TV
- Laptop — Entry-level HP/Lenovo
"""

import re
import json
from decimal import Decimal
from datetime import date
from urllib.parse import quote

from scrapers.base import BaseScraper


class SingerScraper(BaseScraper):
    """
    Scrape appliance and electronics prices from Singer Sri Lanka.
    """

    SOURCE_NAME = "Singer"
    BASE_URL = "https://singersl.com"
    RATE_LIMIT_SECONDS = 3.0

    PRODUCT_SEARCHES = {
        'Paint — Emulsion': ['emulsion paint', 'multilac paint', 'nippon paint'],
        'Refrigerator — Inverter': ['inverter refrigerator 250l', 'samsung refrigerator'],
        'Washing Machine — 7kg': ['washing machine 7kg', 'front load washing machine'],
        'Smartphone — Samsung': ['samsung galaxy a15', 'samsung galaxy a'],
        'Television — 43': ['43 inch smart tv', '43" tv'],
        'Laptop — Entry-level': ['hp laptop', 'lenovo laptop', 'entry level laptop'],
    }

    def scrape(self):
        from core.models import BasketItem

        today = date.today()

        items = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            scrape_source_primary__icontains='singersl',
            is_active=True,
            requires_manual_entry=False,
        )

        for item in items:
            search_terms = self._get_search_terms(item)
            price = None

            for term in search_terms:
                try:
                    price = self._search_and_extract_price(term)
                    if price:
                        break
                except Exception as e:
                    self.log_error(f"Search failed for '{term}': {e}")
                    continue

            if price:
                self.save_price(
                    item=item,
                    price=price,
                    observation_date=today,
                    source_url=item.scrape_source_primary or 'https://singersl.com',
                    source_name='Singer Sri Lanka',
                    raw_data={'search_term_used': term},
                )
            else:
                self.log_error(f"Could not find price for: {item.name}")
                self.items_failed += 1

    def _get_search_terms(self, item) -> list:
        terms = []
        for key, search_list in self.PRODUCT_SEARCHES.items():
            if key.lower() in item.name.lower():
                terms.extend(search_list)

        if not terms:
            words = item.name.replace('—', ' ').replace('-', ' ').replace('"', ' ').split()
            terms.append(' '.join(words[:3]))

        return terms

    def _search_and_extract_price(self, search_term: str) -> Decimal | None:
        try:
            search_url = f"/search?q={quote(search_term)}"
            soup = self.fetch_soup(search_url)
        except Exception as e:
            self.log_error(f"Search page fetch failed: {e}")
            return None

        price_selectors = [
            '.price',
            '.product-price',
            '.current-price',
            '.sale-price',
            '[data-price]',
            '.amount',
            '.woocommerce-Price-amount',
        ]

        for selector in price_selectors:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text(strip=True)
                price = self.parse_price(text)
                if price and price > 0:
                    return price

        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        price_str = offers.get('price')
                        if price_str:
                            price = self.parse_price(str(price_str))
                            if price and price > 0:
                                return price
            except (json.JSONDecodeError, AttributeError):
                continue

        page_text = soup.get_text()
        match = re.search(r'rs\.?\s*([\d,]+\.?\d*)', page_text, re.IGNORECASE)
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 100:
                return price

        return None

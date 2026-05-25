"""
Spar 2U scraper.

Target: https://spar2u.lk
Spar is another major Sri Lankan supermarket with online delivery.
"""

import re
import json
from decimal import Decimal
from datetime import date
from urllib.parse import quote

from scrapers.base import BaseScraper


class SparScraper(BaseScraper):
    """
    Scrape grocery prices from Spar 2U online store.
    Used as a backup source for items that also have Keells as primary.
    """

    SOURCE_NAME = "Spar"
    BASE_URL = "https://spar2u.lk"
    RATE_LIMIT_SECONDS = 3.0

    PRODUCT_SEARCHES = {
        'Rice — Nadu': ['nadu rice'],
        'Rice — Samba': ['samba rice'],
        'Wheat Flour — Prima': ['prima wheat flour'],
        'Dhal (Mysoor': ['mysoor dhal'],
        'Sugar — White': ['white sugar'],
        'Coconut Oil': ['coconut oil'],
        'Eggs — Fresh': ['eggs'],
        'Chicken — Whole': ['whole chicken'],
        'Milk Powder — Anchor': ['anchor milk powder'],
        'Tea — Loose': ['loose tea'],
        'Soap — Lux': ['lux soap'],
        'Shampoo — Sunsilk': ['sunsilk shampoo'],
        'Toothpaste — Signal': ['signal toothpaste'],
    }

    def scrape(self):
        from core.models import BasketItem

        today = date.today()

        items = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            scrape_source_backup__icontains='spar2u',
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
                    source_url=item.scrape_source_backup or 'https://spar2u.lk',
                    source_name='Spar 2U',
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
            words = item.name.replace('—', ' ').replace('-', ' ').split()
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
            if price and price > 10:
                return price

        return None

"""
Keells Super scraper.

Target: https://keellssuper.com
Keells is a major Sri Lankan supermarket chain with an online store.
Product pages are accessible via URL patterns like:
  https://keellssuper.com/product/{product-slug}

Strategy:
1. Try to hit the site homepage to get a session cookie
2. Search for products using their search API
3. Parse product detail pages for prices

Note: Keells may use Cloudflare or similar bot protection.
If scraping fails, items should fall back to manual entry.
"""

import re
import json
from decimal import Decimal
from datetime import date
from urllib.parse import quote

from scrapers.base import BaseScraper


class KeellsScraper(BaseScraper):
    """
    Scrape grocery prices from Keells Super online store.
    """

    SOURCE_NAME = "Keells"
    BASE_URL = "https://keellssuper.com"
    RATE_LIMIT_SECONDS = 3.0  # Be respectful to e-commerce site

    # Mapping of basket item search terms to expected results
    PRODUCT_SEARCHES = {
        'Rice — Nadu': ['nadu rice', 'white nadu rice'],
        'Rice — Samba': ['samba rice'],
        'Wheat Flour — Prima': ['prima wheat flour', 'wheat flour'],
        'Dhal (Mysoor': ['mysoor dhal', 'red lentil'],
        'Sugar — White': ['white sugar', 'granulated sugar'],
        'Coconut Oil': ['coconut oil'],
        'Eggs — Fresh': ['eggs', 'hen eggs'],
        'Chicken — Whole': ['whole chicken', 'dressed chicken'],
        'Milk Powder — Anchor': ['anchor milk powder', 'full cream milk powder'],
        'Tea — Loose': ['loose tea', 'tea leaves'],
        'Dishwashing Liquid': ['vim dishwashing', 'sunlight dishwashing'],
        'Paracetamol': ['panadol', 'paracetamol'],
        'Stationery — A4': ['a4 paper', 'copy paper'],
        'Soap — Lux': ['lux soap', 'lifebuoy soap'],
        'Shampoo — Sunsilk': ['sunsilk shampoo', 'head shoulders shampoo'],
        'Toothpaste — Signal': ['signal toothpaste', 'colgate toothpaste'],
    }

    def scrape(self):
        from core.models import BasketItem

        today = date.today()

        # Get all active Keells basket items
        items = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            scrape_source_primary__icontains='keellssuper',
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
                    source_url=item.scrape_source_primary or 'https://keellssuper.com',
                    source_name='Keells Super',
                    raw_data={'search_term_used': term},
                )
            else:
                self.log_error(f"Could not find price for: {item.name}")
                self.items_failed += 1

    def _get_search_terms(self, item) -> list:
        """Build search terms from item name."""
        terms = []
        for key, search_list in self.PRODUCT_SEARCHES.items():
            if key.lower() in item.name.lower():
                terms.extend(search_list)

        # Fallback: use item name words
        if not terms:
            words = item.name.replace('—', ' ').replace('-', ' ').split()
            terms.append(' '.join(words[:3]))

        return terms

    def _search_and_extract_price(self, search_term: str) -> Decimal | None:
        """
        Search Keells for a product and extract the first product's price.
        
        Keells search URL pattern (observed):
          https://keellssuper.com/search?q={term}
        """
        try:
            search_url = f"/search?q={quote(search_term)}"
            soup = self.fetch_soup(search_url)
        except Exception as e:
            self.log_error(f"Search page fetch failed: {e}")
            return None

        # Look for product price in search results
        # Common patterns: .price, .product-price, data-price, etc.
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

        # Fallback: look for JSON-LD product data
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
                    elif isinstance(offers, list):
                        for offer in offers:
                            price_str = offer.get('price')
                            if price_str:
                                price = self.parse_price(str(price_str))
                                if price and price > 0:
                                    return price
            except (json.JSONDecodeError, AttributeError):
                continue

        # Fallback: regex search for price patterns in HTML
        page_text = soup.get_text()
        match = re.search(r'rs\.?\s*([\d,]+\.?\d*)', page_text, re.IGNORECASE)
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 10:
                return price

        return None

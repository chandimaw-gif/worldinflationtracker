"""
CEYPETCO fuel price scraper.

Target: https://ceypetco.gov.lk/historical-prices/
CEYPETCO publishes historical fuel prices in a table format.
We scrape the most recent entry for:
- Petrol Octane 92
- Petrol Octane 95
- Auto Diesel
"""

import re
from decimal import Decimal
from datetime import datetime, date

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper


class CEYPETCOScraper(BaseScraper):
    """
    Scrape latest fuel prices from CEYPETCO historical prices page.
    """

    SOURCE_NAME = "CEYPETCO"
    BASE_URL = "https://ceypetco.gov.lk"
    RATE_LIMIT_SECONDS = 2.0

    # Mapping of basket item name fragments to table column text fragments
    FUEL_MAP = {
        'Petrol — Octane 92': ['LP 92', '92'],
        'Petrol — Octane 95': ['LP 95', '95'],
        'Auto Diesel': ['LAD', 'AUTO DIESEL', 'DIESEL'],
    }

    def scrape(self):
        from core.models import BasketItem

        today = date.today()

        try:
            soup = self.fetch_soup('/historical-prices/')
        except Exception as e:
            self.log_error(f"Failed to fetch CEYPETCO page: {e}")
            self.items_failed += 3  # One per fuel type
            return

        # The page has a table with columns:
        # Date | LP 95 | LP 92 | LAD | LSD | LK | LIK | FUR. 800 | FUR 1500 (High) | FUR. 1500 (Low)
        latest_prices = self._extract_latest_prices(soup)

        if not latest_prices:
            self.log_error("Could not extract any fuel prices from CEYPETCO table")
            self.items_failed += 3
            return

        # Match and save each fuel type
        for item_name_fragments, column_frags in self.FUEL_MAP.items():
            item = BasketItem.objects.filter(
                country__code=self.COUNTRY_CODE,
                name__icontains=item_name_fragments.split(' — ')[0],
                is_active=True,
            ).first()

            if not item:
                self.log_error(f"Basket item not found for: {item_name_fragments}")
                self.items_failed += 1
                continue

            # Find matching price
            price = None
            matched_col = None
            for col_key, col_price in latest_prices.items():
                if col_key.startswith('_'):
                    continue
                col_upper = col_key.upper()
                for frag in column_frags:
                    if frag.upper() in col_upper:
                        price = col_price
                        matched_col = col_key
                        break
                if price:
                    break

            if price:
                self.save_price(
                    item=item,
                    price=price,
                    observation_date=today,
                    source_url='https://ceypetco.gov.lk/historical-prices/',
                    source_name='CEYPETCO',
                    raw_data={
                        'column_matched': matched_col,
                        'effective_date': latest_prices.get('_effective_date', str(today)),
                    },
                )
            else:
                self.log_error(f"Could not find price for {item_name_fragments} in columns: {list(latest_prices.keys())}")
                self.items_failed += 1

    def _extract_latest_prices(self, soup: BeautifulSoup) -> dict:
        """
        Extract the most recent row from the fuel prices table.
        Returns a dict mapping column header -> price.
        """
        best_result = {}

        tables = soup.find_all('table')
        for table in tables:
            # Find header row
            header_row = table.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            else:
                # Try first tr with th cells
                headers = []
                for tr in table.find_all('tr'):
                    th_cells = tr.find_all('th')
                    if th_cells:
                        headers = [th.get_text(strip=True) for th in th_cells]
                        break

            if not headers:
                continue

            header_text = ' '.join(headers).upper()
            # Skip lubricant / non-fuel tables
            if 'CIRCULAR' in header_text or 'DRUM' in header_text:
                continue
            # Must have fuel-related headers
            if not any(x in header_text for x in ['LP 92', 'LP 95', 'LAD', 'PETROL', 'DIESEL', 'FUEL']):
                continue

            # Find the first data row (most recent)
            tbody = table.find('tbody')
            rows = tbody.find_all('tr') if tbody else table.find_all('tr')
            data_rows = [r for r in rows if r.find('td')]

            if not data_rows:
                continue

            result = {}
            latest_row = data_rows[0]
            cells = latest_row.find_all('td')

            for i, cell in enumerate(cells):
                if i >= len(headers):
                    break
                header = headers[i]
                text = cell.get_text(strip=True)

                # First column is usually the effective date
                if i == 0:
                    result['_effective_date'] = text
                    continue

                price = self.parse_price(text)
                if price and price > 0:
                    result[header] = price

            # Keep the table with the most fuel price columns
            if len(result) > len(best_result):
                best_result = result

        return best_result

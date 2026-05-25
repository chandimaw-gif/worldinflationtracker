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
        'Petrol — Octane 92': ['92', 'OCTANE 92', 'PETROL 92'],
        'Petrol — Octane 95': ['95', 'OCTANE 95', 'PETROL 95', 'XTRA MILE 95'],
        'Auto Diesel': ['DIESEL', 'AUTO DIESEL', 'LAD'],
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

        # The page usually has a table with columns:
        # Effective Date | Lanka Petrol 92 Octane | Lanka Petrol 95 Octane | Lanka Auto Diesel | ...
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
            for col_key, col_price in latest_prices.items():
                col_upper = col_key.upper()
                for frag in column_frags:
                    if frag.upper() in col_upper:
                        price = col_price
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
                        'column_matched': col_key,
                        'effective_date': latest_prices.get('_effective_date', str(today)),
                    },
                )
            else:
                self.log_error(f"Could not find price for {item_name_fragments} in columns: {list(latest_prices.keys())}")
                self.items_failed += 1

    def _extract_latest_prices(self, soup: BeautifulSoup) -> dict:
        """
        Extract the most recent row from the historical prices table.
        Returns a dict mapping column header -> price.
        """
        result = {}

        tables = soup.find_all('table')
        for table in tables:
            # Find header row
            header_row = table.find('thead')
            if not header_row:
                # Try first tr with th cells
                for tr in table.find_all('tr'):
                    if tr.find('th'):
                        header_row = tr
                        break

            if not header_row:
                continue

            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

            # Find the first data row (most recent)
            tbody = table.find('tbody')
            rows = tbody.find_all('tr') if tbody else table.find_all('tr')
            data_rows = [r for r in rows if r.find('td')]

            if not data_rows:
                continue

            latest_row = data_rows[0]
            cells = latest_row.find_all('td')

            if len(cells) != len(headers):
                # Sometimes there are colspan/rowspan issues; try anyway
                pass

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

            if result:
                break

        return result

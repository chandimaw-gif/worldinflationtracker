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


# Regex patterns for CEYPETCO fuel price extraction
# Matches: <tr><td>03.05.2026</td><td>470</td><td>410</td>...
CEYPETCO_ROW_RE = re.compile(
    r'<tr>\s*<td>(\d{2}\.\d{2}\.\d{4})</td>'
    r'((?:\s*<td>([\d.]+)</td>)*)'
    r'\s*</tr>',
    re.IGNORECASE
)
CEYPETCO_CELL_RE = re.compile(r'<td>([\d.]+)</td>', re.IGNORECASE)
CEYPETCO_HEADER_RE = re.compile(r'<th>([^<]+)</th>', re.IGNORECASE)


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
        Uses regex on raw HTML (most reliable for CEYPETCO's encoding).
        Returns a dict mapping column header -> price.
        """
        return self._extract_via_regex()

    def _extract_via_regex(self) -> dict:
        """
        Fallback regex-based extraction from raw HTML.
        CEYPETCO's page sometimes has encoding issues that break BS4.
        """
        try:
            resp = self.session.get(
                'https://ceypetco.gov.lk/historical-prices/',
                timeout=self.DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            self.log_error(f"Regex fallback fetch failed: {e}")
            return {}

        # Find all header rows
        all_headers = []
        for table_match in re.finditer(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE):
            table_html = table_match.group(1)
            headers = CEYPETCO_HEADER_RE.findall(table_html)
            if headers:
                all_headers.append((table_html, headers))

        # Pick the table with fuel-related headers
        best_table = None
        best_headers = None
        for table_html, headers in all_headers:
            header_text = ' '.join(headers).upper()
            if 'CIRCULAR' in header_text or 'DRUM' in header_text:
                continue
            if any(x in header_text for x in ['LP 92', 'LP 95', 'LAD']):
                best_table = table_html
                best_headers = headers
                break

        if not best_table or not best_headers:
            return {}

        # Find the first data row in this table
        rows = CEYPETCO_ROW_RE.findall(best_table)
        if not rows:
            return {}

        # rows[0] = (date_string, td_block, ...)
        date_str = rows[0][0]
        td_block = rows[0][1]
        cell_values = CEYPETCO_CELL_RE.findall(td_block)

        result = {'_effective_date': date_str}
        for i, val in enumerate(cell_values):
            if i + 1 >= len(best_headers):
                break
            header = best_headers[i + 1]  # skip Date column
            price = self.parse_price(val)
            if price and price > 0:
                result[header] = price

        return result

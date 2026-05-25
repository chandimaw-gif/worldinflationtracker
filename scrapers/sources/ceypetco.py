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
        latest_prices = self._extract_via_regex()

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

    def _extract_via_regex(self) -> dict:
        """
        Regex-based extraction from raw HTML.
        CEYPETCO's page has encoding issues that break BS4.
        """
        try:
            resp = self.session.get(
                'https://ceypetco.gov.lk/historical-prices/',
                timeout=self.DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            html = resp.content.decode('utf-8', errors='replace')
        except Exception as e:
            self.log_error(f"Regex fetch failed: {e}")
            return {}

        HEADER_RE = re.compile(r'<th>([^<]+)</th>', re.IGNORECASE)
        ROW_RE = re.compile(
            r'<tr>\s*<td>(\d{2}\.\d{2}\.\d{4})</td>'
            r'((?:\s*<td>([\d.]+)</td>)*)'
            r'\s*</tr>',
            re.IGNORECASE
        )
        CELL_RE = re.compile(r'<td>([\d.]+)</td>', re.IGNORECASE)

        # Find all tables with headers
        all_headers = []
        for table_match in re.finditer(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE):
            table_html = table_match.group(1)
            headers = HEADER_RE.findall(table_html)
            if headers:
                all_headers.append((table_html, headers))

        # Pick the fuel price table
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

        # Extract the first data row
        rows = ROW_RE.findall(best_table)
        if not rows:
            return {}

        date_str = rows[0][0]
        td_block = rows[0][1]
        cell_values = CELL_RE.findall(td_block)

        result = {'_effective_date': date_str}
        for i, val in enumerate(cell_values):
            if i + 1 >= len(best_headers):
                break
            header = best_headers[i + 1]
            price = self.parse_price(val)
            if price and price > 0:
                result[header] = price

        return result

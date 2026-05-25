"""
Central Bank of Sri Lanka (CBSL) scraper.

Targets:
- USD/LKR exchange rate (daily)
- Gold price (daily) — derived from exchange rate page or dedicated page
"""

import re
from decimal import Decimal
from datetime import datetime, date

from scrapers.base import BaseScraper


class CBSLExchangeRateScraper(BaseScraper):
    """
    Scrape USD/LKR exchange rate from CBSL.
    CBSL publishes daily exchange rates at:
    https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates
    """

    SOURCE_NAME = "CBSL"
    BASE_URL = "https://www.cbsl.gov.lk"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        today = date.today()

        # CBSL sometimes blocks scraping; try the main exchange rate page
        try:
            soup = self.fetch_soup('/en/rates-and-indicators/exchange-rates')
        except Exception as e:
            self.log_error(f"Failed to fetch exchange rate page: {e}")
            # Fallback: try the API/JSON endpoint if available
            return self._scrape_via_api(today)

        # Look for USD rate in tables
        usd_rate = self._extract_usd_from_html(soup)
        if usd_rate:
            self.save_exchange_rate(
                rate_date=today,
                rate=usd_rate,
                base_currency='USD',
                local_currency='LKR',
                source='CBSL Exchange Rate Page',
            )
        else:
            self.log_error("Could not extract USD/LKR rate from HTML")
            self.items_failed += 1

    def _extract_usd_from_html(self, soup) -> Decimal | None:
        """Parse USD buying/selling rate from the exchange rate table."""
        # CBSL tables usually have rows with currency codes
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                text = ' '.join(c.get_text(strip=True).upper() for c in cells)
                if 'USD' in text or 'U.S.' in text:
                    # Try to find numeric values in the row
                    for cell in cells:
                        price = self.parse_price(cell.get_text())
                        if price and price > 100:  # USD/LKR should be > 100
                            return price
        return None

    def _scrape_via_api(self, rate_date: date):
        """
        Fallback: CBSL sometimes provides a CSV or JSON feed.
        This is a placeholder for future API integration.
        """
        self.log_error("API fallback not yet implemented")
        self.items_failed += 1


class CBSLGoldScraper(BaseScraper):
    """
    Scrape gold price from CBSL or a reliable local source.
    CBSL publishes gold prices at:
    https://www.cbsl.gov.lk/en/rates-and-indicators/price-gold
    """

    SOURCE_NAME = "CBSL_Gold"
    BASE_URL = "https://www.cbsl.gov.lk"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        from core.models import BasketItem

        today = date.today()
        try:
            soup = self.fetch_soup('/en/rates-and-indicators/price-gold')
        except Exception as e:
            self.log_error(f"Failed to fetch gold price page: {e}")
            self.items_failed += 1
            return

        # Look for 22-carat gold price per gram
        gold_price = self._extract_22k_gold_price(soup)
        if gold_price:
            item = BasketItem.objects.filter(
                country__code=self.COUNTRY_CODE,
                name__icontains='gold',
                is_active=True,
            ).filter(
                name__icontains='22',
            ).first()

            if item:
                self.save_price(
                    item=item,
                    price=gold_price,
                    observation_date=today,
                    source_url='https://www.cbsl.gov.lk/en/rates-and-indicators/price-gold',
                    source_name='CBSL Gold Price',
                    raw_data={'carat': '22', 'unit': 'per gram'},
                )
            else:
                self.log_error("Gold basket item not found")
                self.items_failed += 1
        else:
            self.log_error("Could not extract 22k gold price from HTML")
            self.items_failed += 1

    def _extract_22k_gold_price(self, soup) -> Decimal | None:
        """Extract 22-carat gold price per gram from the page."""
        # Look for tables or paragraphs containing "22" and gold price
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                text = ' '.join(c.get_text(strip=True).upper() for c in cells)
                if '22' in text and ('GOLD' in text or 'PER GRAM' in text or 'PER 1G' in text):
                    for cell in cells:
                        price = self.parse_price(cell.get_text())
                        if price and price > 1000:  # Gold should be > 1000 LKR/g
                            return price

        # Fallback: search all text for patterns like "22 Carat - Rs. 15,250"
        page_text = soup.get_text()
        match = re.search(r'22\s*[Kk]\s*(?:carat)?.*?Rs\.?\s*([\d,]+\.?\d*)', page_text, re.IGNORECASE)
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 1000:
                return price

        return None

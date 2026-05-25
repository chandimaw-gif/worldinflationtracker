"""
Utility price scrapers for Sri Lanka.

Targets:
- CEB electricity tariffs (monthly)
- Litro Gas 12.5kg cylinder (daily)
- Laugfs Gas 12.5kg cylinder (daily)
- Dialog mobile plans (weekly)
- SLT broadband plans (monthly)
"""

import re
from decimal import Decimal
from datetime import date

from scrapers.base import BaseScraper


class CEBTariffScraper(BaseScraper):
    """
    Scrape CEB domestic electricity tariff.
    https://www.ceb.lk/tariff_catergory
    """

    SOURCE_NAME = "CEB"
    BASE_URL = "https://www.ceb.lk"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        from core.models import BasketItem

        today = date.today()
        item = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            name__icontains='Electricity tariff',
            is_active=True,
        ).first()

        if not item:
            self.log_error("CEB electricity basket item not found")
            self.items_failed += 1
            return

        try:
            soup = self.fetch_soup('/tariff_catergory')
        except Exception as e:
            self.log_error(f"Failed to fetch CEB tariff page: {e}")
            self.items_failed += 1
            return

        # CEB tariffs are usually in tables. Look for "Domestic" and "0-60" or per-kWh rates.
        rate = self._extract_domestic_rate(soup)

        if rate:
            self.save_price(
                item=item,
                price=rate,
                observation_date=today,
                source_url='https://www.ceb.lk/tariff_catergory',
                source_name='CEB',
                raw_data={'tariff_block': '0-60 kWh domestic'},
            )
        else:
            self.log_error("Could not extract CEB domestic tariff rate")
            self.items_failed += 1

    def _extract_domestic_rate(self, soup) -> Decimal | None:
        """Extract the domestic 0-60 kWh per-unit rate."""
        # Look for tables containing tariff information
        tables = soup.find_all('table')
        for table in tables:
            text = table.get_text().upper()
            if 'DOMESTIC' in text or '0-60' in text or 'PER UNIT' in text:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    row_text = ' '.join(c.get_text(strip=True) for c in cells).upper()

                    # Look for 0-60 kWh block
                    if '0-60' in row_text or '0_60' in row_text or 'FIRST 60' in row_text:
                        for cell in cells:
                            price = self.parse_price(cell.get_text())
                            if price and 5 < price < 100:  # CEB domestic rate should be in this range
                                return price

        # Fallback: search entire page for patterns like "Rs. 12.50 per unit" near "Domestic"
        page_text = soup.get_text()
        match = re.search(
            r'domestic.*?0[-\s]60.*?rs\.?\s*([\d,]+\.?\d*)',
            page_text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            price = self.parse_price(match.group(1))
            if price and 5 < price < 100:
                return price

        return None


class LitroGasScraper(BaseScraper):
    """
    Scrape Litro Gas 12.5kg cylinder price.
    https://www.litrogas.com/price-list/
    """

    SOURCE_NAME = "Litro_Gas"
    BASE_URL = "https://www.litrogas.com"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        from core.models import BasketItem

        today = date.today()
        item = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            name__icontains='Litro',
            name__icontains='12.5kg',
            is_active=True,
        ).first()

        if not item:
            self.log_error("Litro Gas basket item not found")
            self.items_failed += 1
            return

        try:
            soup = self.fetch_soup('/price-list/')
        except Exception as e:
            self.log_error(f"Failed to fetch Litro price page: {e}")
            self.items_failed += 1
            return

        price = self._extract_12_5kg_price(soup)

        if price:
            self.save_price(
                item=item,
                price=price,
                observation_date=today,
                source_url='https://www.litrogas.com/price-list/',
                source_name='Litro Gas',
                raw_data={'cylinder_size': '12.5kg'},
            )
        else:
            self.log_error("Could not extract Litro 12.5kg price")
            self.items_failed += 1

    def _extract_12_5kg_price(self, soup) -> Decimal | None:
        """Extract 12.5kg domestic cylinder price."""
        # Litro price lists are often in tables or list items
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_text = ' '.join(c.get_text(strip=True) for c in cells).upper()
                if '12.5' in row_text or '12.5KG' in row_text or 'DOMESTIC' in row_text:
                    for cell in cells:
                        price = self.parse_price(cell.get_text())
                        if price and price > 1000:  # Gas cylinder > 1000 LKR
                            return price

        # Fallback: search all text
        page_text = soup.get_text()
        match = re.search(
            r'12\.5\s*kg.*?rs\.?\s*([\d,]+\.?\d*)',
            page_text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 1000:
                return price

        return None


class LaugfsGasScraper(BaseScraper):
    """
    Scrape Laugfs Gas 12.5kg cylinder price.
    https://www.laugfsgas.lk/pricelist.php
    """

    SOURCE_NAME = "Laugfs_Gas"
    BASE_URL = "https://www.laugfsgas.lk"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        from core.models import BasketItem

        today = date.today()
        item = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            name__icontains='Laugfs',
            name__icontains='12.5kg',
            is_active=True,
        ).first()

        if not item:
            self.log_error("Laugfs Gas basket item not found")
            self.items_failed += 1
            return

        try:
            soup = self.fetch_soup('/pricelist.php')
        except Exception as e:
            self.log_error(f"Failed to fetch Laugfs price page: {e}")
            self.items_failed += 1
            return

        price = self._extract_12_5kg_price(soup)

        if price:
            self.save_price(
                item=item,
                price=price,
                observation_date=today,
                source_url='https://www.laugfsgas.lk/pricelist.php',
                source_name='Laugfs Gas',
                raw_data={'cylinder_size': '12.5kg'},
            )
        else:
            self.log_error("Could not extract Laugfs 12.5kg price")
            self.items_failed += 1

    def _extract_12_5kg_price(self, soup) -> Decimal | None:
        """Extract 12.5kg domestic cylinder price from Laugfs."""
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_text = ' '.join(c.get_text(strip=True) for c in cells).upper()
                if '12.5' in row_text or '12.5KG' in row_text or 'DOMESTIC' in row_text:
                    for cell in cells:
                        price = self.parse_price(cell.get_text())
                        if price and price > 1000:
                            return price

        page_text = soup.get_text()
        match = re.search(
            r'12\.5\s*kg.*?rs\.?\s*([\d,]+\.?\d*)',
            page_text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 1000:
                return price

        return None


class DialogScraper(BaseScraper):
    """
    Scrape Dialog mobile plans.
    https://dialog.lk/mobile/prepaid/plans
    https://dialog.lk/mobile-broadband/prepaid/plan
    """

    SOURCE_NAME = "Dialog"
    BASE_URL = "https://dialog.lk"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        from core.models import BasketItem

        today = date.today()

        # Scrape voice rate
        voice_item = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            name__icontains='Dialog',
            name__icontains='voice',
            is_active=True,
        ).first()

        data_item = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            name__icontains='Dialog',
            name__icontains='data',
            is_active=True,
        ).first()

        if voice_item:
            self._scrape_voice_rate(voice_item, today)
        else:
            self.log_error("Dialog voice basket item not found")
            self.items_failed += 1

        if data_item:
            self._scrape_data_rate(data_item, today)
        else:
            self.log_error("Dialog data basket item not found")
            self.items_failed += 1

    def _scrape_voice_rate(self, item, today: date):
        try:
            soup = self.fetch_soup('/mobile/prepaid/plans')
        except Exception as e:
            self.log_error(f"Failed to fetch Dialog voice page: {e}")
            self.items_failed += 1
            return

        rate = self._extract_per_minute_rate(soup)
        if rate:
            self.save_price(
                item=item,
                price=rate,
                observation_date=today,
                source_url='https://dialog.lk/mobile/prepaid/plans',
                source_name='Dialog',
                raw_data={'rate_type': 'per minute voice'},
            )
        else:
            self.log_error("Could not extract Dialog per-minute voice rate")
            self.items_failed += 1

    def _scrape_data_rate(self, item, today: date):
        try:
            soup = self.fetch_soup('/mobile-broadband/prepaid/plan')
        except Exception as e:
            self.log_error(f"Failed to fetch Dialog data page: {e}")
            self.items_failed += 1
            return

        rate = self._extract_data_package_rate(soup)
        if rate:
            self.save_price(
                item=item,
                price=rate,
                observation_date=today,
                source_url='https://dialog.lk/mobile-broadband/prepaid/plan',
                source_name='Dialog',
                raw_data={'rate_type': '1.5GB monthly add-on'},
            )
        else:
            self.log_error("Could not extract Dialog data package rate")
            self.items_failed += 1

    def _extract_per_minute_rate(self, soup) -> Decimal | None:
        """Extract per-minute voice call rate."""
        page_text = soup.get_text()
        # Common patterns: "Rs. 1.50 per minute", "LKR 2/min"
        match = re.search(
            r'(?:rs\.?|lkr)\s*([\d,]+\.?\d*)\s*(?:per\s*min|/min)',
            page_text,
            re.IGNORECASE
        )
        if match:
            price = self.parse_price(match.group(1))
            if price and 0.5 < price < 50:
                return price
        return None

    def _extract_data_package_rate(self, soup) -> Decimal | None:
        """Extract 1.5GB monthly add-on price."""
        page_text = soup.get_text()
        # Look for "1.5GB" or "1.5 GB" near a price
        match = re.search(
            r'1\.5\s*gb.*?rs\.?\s*([\d,]+\.?\d*)',
            page_text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 50:
                return price

        # Fallback: generic data package price
        match = re.search(
            r'(?:data\s*package|add-on).*?rs\.?\s*([\d,]+\.?\d*)',
            page_text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 50:
                return price

        return None


class SLTScraper(BaseScraper):
    """
    Scrape SLT Fibre broadband 30Mbps plan price.
    https://www.slt.lk
    """

    SOURCE_NAME = "SLT"
    BASE_URL = "https://www.slt.lk"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        from core.models import BasketItem

        today = date.today()
        item = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            name__icontains='SLT',
            name__icontains='Fibre',
            is_active=True,
        ).first()

        if not item:
            self.log_error("SLT Fibre basket item not found")
            self.items_failed += 1
            return

        try:
            soup = self.fetch_soup('/')
        except Exception as e:
            self.log_error(f"Failed to fetch SLT page: {e}")
            self.items_failed += 1
            return

        price = self._extract_30mbps_price(soup)

        if price:
            self.save_price(
                item=item,
                price=price,
                observation_date=today,
                source_url='https://www.slt.lk',
                source_name='SLT',
                raw_data={'plan': 'Fibre 30Mbps monthly'},
            )
        else:
            self.log_error("Could not extract SLT 30Mbps plan price")
            self.items_failed += 1

    def _extract_30mbps_price(self, soup) -> Decimal | None:
        """Extract 30Mbps fibre plan monthly price."""
        page_text = soup.get_text()
        # Look for "30Mbps" or "30 Mbps" near a price
        match = re.search(
            r'30\s*mbps.*?rs\.?\s*([\d,]+\.?\d*)',
            page_text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 500:
                return price

        # Fallback: look for broadband prices
        match = re.search(
            r'(?:fibre|broadband).*?rs\.?\s*([\d,]+\.?\d*)',
            page_text,
            re.IGNORECASE | re.DOTALL
        )
        if match:
            price = self.parse_price(match.group(1))
            if price and price > 500:
                return price

        return None

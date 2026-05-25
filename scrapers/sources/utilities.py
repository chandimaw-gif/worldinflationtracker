"""
Utility price scrapers for Sri Lanka.

Targets:
- CEB electricity tariffs (monthly)
- Litro Gas 12.5kg cylinder (daily) — JS-rendered, manual entry fallback
- Laugfs Gas 12.5kg cylinder (daily)
- Dialog mobile plans (weekly) — data works, voice needs manual entry
- SLT broadband plans (monthly) — JS-rendered, manual entry fallback
"""

import re
from decimal import Decimal
from datetime import date

from scrapers.base import BaseScraper


class CEBTariffScraper(BaseScraper):
    """
    Scrape CEB domestic electricity tariff.
    https://www.ceb.lk/tariff_catergory
    The page uses responsive CSS tables with class-based cells.
    """

    SOURCE_NAME = "CEB"
    BASE_URL = "https://www.ceb.lk"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        import requests
        from bs4 import BeautifulSoup
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
            resp = requests.get(
                'https://www.ceb.lk/tariff_catergory',
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=self.DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
        except Exception as e:
            self.log_error(f"Failed to fetch CEB tariff page: {e}")
            self.items_failed += 1
            return

        rate = self._extract_domestic_rate(soup)

        if rate:
            self.save_price(
                item=item,
                price=rate,
                observation_date=today,
                source_url='https://www.ceb.lk/tariff_catergory',
                source_name='CEB',
                raw_data={'tariff_block': '0-30 kWh domestic', 'unit': 'Rs/kWh'},
            )
        else:
            self.log_error("Could not extract CEB domestic tariff rate")
            self.items_failed += 1

    def _extract_domestic_rate(self, soup) -> Decimal | None:
        """Extract the domestic 0-30 kWh per-unit rate from table_1."""
        all_cells = soup.find_all('td', class_='table_1')
        for i, cell in enumerate(all_cells):
            text = cell.get_text(strip=True)
            if '0' in text and '30' in text:
                if i + 1 < len(all_cells):
                    charge_cell = all_cells[i + 1]
                    price = self.parse_price(charge_cell.get_text())
                    if price and 1 < price < 50:
                        return price
        return None


class LitroGasScraper(BaseScraper):
    """
    Litro Gas prices are loaded via JavaScript on their WordPress page.
    This scraper falls back to manual entry.
    https://www.litrogas.com/price-list/
    """

    SOURCE_NAME = "Litro_Gas"
    BASE_URL = "https://www.litrogas.com"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        self.log_error(
            "Litro Gas price-list page loads prices via JavaScript. "
            "Please enter manually via: python manage.py enter_prices --item 'Litro' --price <PRICE>"
        )
        self.items_failed += 1


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
            is_active=True,
        ).filter(
            name__icontains='12.5kg',
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
                raw_data={'cylinder_size': '12.5kg', 'district': 'Colombo'},
            )
        else:
            self.log_error("Could not extract Laugfs 12.5kg price")
            self.items_failed += 1

    def _extract_12_5kg_price(self, soup) -> Decimal | None:
        """Extract 12.5kg domestic cylinder price from Laugfs."""
        # Find the table with "12.5kg (Rs)" header
        tables = soup.find_all('table')
        for table in tables:
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            if not any('12.5' in h for h in headers):
                continue

            # Find the 12.5kg column index
            col_idx = None
            for i, h in enumerate(headers):
                if '12.5' in h:
                    col_idx = i
                    break

            if col_idx is None:
                continue

            # Get the first data row
            for tr in table.find_all('tr'):
                cells = tr.find_all('td')
                if len(cells) > col_idx:
                    price = self.parse_price(cells[col_idx].get_text())
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

        # Scrape voice rate — Dialog bundles don't show a simple per-minute rate
        voice_item = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            name__icontains='Dialog',
            is_active=True,
        ).filter(
            name__icontains='voice',
        ).first()

        data_item = BasketItem.objects.filter(
            country__code=self.COUNTRY_CODE,
            name__icontains='Dialog',
            is_active=True,
        ).filter(
            name__icontains='data',
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
        self.log_error(
            "Dialog prepaid plans are bundle-based; no simple per-minute rate displayed. "
            "Please enter manually via: python manage.py enter_prices --item 'Dialog voice' --price <PRICE>"
        )
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
    SLT Fibre broadband prices are loaded via JavaScript.
    Falls back to manual entry.
    https://www.slt.lk
    """

    SOURCE_NAME = "SLT"
    BASE_URL = "https://www.slt.lk"
    RATE_LIMIT_SECONDS = 2.0

    def scrape(self):
        self.log_error(
            "SLT Fibre prices are loaded via JavaScript. "
            "Please enter manually via: python manage.py enter_prices --item 'SLT Fibre' --price <PRICE>"
        )
        self.items_failed += 1

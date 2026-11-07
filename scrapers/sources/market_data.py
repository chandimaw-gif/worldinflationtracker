"""
Scrapers for market data:
- CBSL indicative exchange rates
- CBSL interest rates (AWPLR, TBill, SDFR, SLFR, OPR)
- Commercial bank exchange rates
- US Treasury yields
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from scrapers.base import BaseScraper
from core.models import ExchangeRate, MarketRate, BankExchangeRate, Country


class CBSLMarketRateScraper(BaseScraper):
    """Scrape CBSL indicative exchange rates and interest rates."""
    SOURCE_NAME = "CBSL Market Rates"
    BASE_URL = "https://www.cbsl.gov.lk"

    def scrape(self):
        country = Country.objects.get(code='LKA')

        # Interest rates from CBSL rates page
        # (USD/LKR exchange rate is handled by fetch_daily_cbsl_exchange_rate)
        try:
            count = self._scrape_interest_rates(country)
        except Exception as e:
            self.errors.append(f"Interest rate scrape failed: {e}")
            count = 0

        self.items_scraped = count
        self.status = 'success' if count > 0 else 'failed'

    def _scrape_exchange_rate(self, country):
        """Fetch USD/LKR indicative rate from CBSL API page."""
        # CBSL has a rates indicators page; we'll scrape the indicative rate
        url = f"{self.BASE_URL}/en/rates-and-indicators/exchange-rates"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # Look for USD rate in the page
        # Typical format: USD = 295.75 or similar patterns
        patterns = [
            r'USD\s*[=:]\s*([0-9,]+\.\d{2,4})',
            r'US\s*Dollar.*?([0-9,]+\.\d{2,4})',
            r'Indicative.*?USD.*?([0-9,]+\.\d{2,4})',
        ]

        rate = None
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
            if m:
                try:
                    rate = Decimal(m.group(1).replace(',', ''))
                    break
                except InvalidOperation:
                    continue

        if rate is None:
            raise ValueError("Could not find USD/LKR rate on CBSL page")

        ExchangeRate.objects.update_or_create(
            country=country,
            rate_date=date.today(),
            base_currency='USD',
            defaults={
                'local_currency': 'LKR',
                'rate': rate,
                'source': 'CBSL Indicative',
            }
        )

    def _scrape_interest_rates(self, country):
        """Scrape AWPLR, TBill rates from CBSL."""
        url = f"{self.BASE_URL}/en/rates-and-indicators/interest-rates"
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        html = resp.text

        count = 0
        today = date.today()

        # Map of patterns to rate types
        patterns = {
            'awplr': [
                r'AWPLR.*?([0-9]+\.\d{2})',
                r'Average\s*Weighted\s*Prime\s*Lending\s*Rate.*?([0-9]+\.\d{2})',
            ],
            'tbill_91': [
                r'91[\s\-]*day.*?([0-9]+\.\d{2})',
                r'3[\s\-]*Month.*?([0-9]+\.\d{2})',
            ],
            'tbill_182': [
                r'182[\s\-]*day.*?([0-9]+\.\d{2})',
                r'6[\s\-]*Month.*?([0-9]+\.\d{2})',
            ],
            'tbill_364': [
                r'364[\s\-]*day.*?([0-9]+\.\d{2})',
                r'12[\s\-]*Month.*?([0-9]+\.\d{2})',
            ],
            'sdfr': [
                r'SDFR.*?([0-9]+\.\d{2})',
                r'Standing\s*Deposit\s*Facility\s*Rate.*?([0-9]+\.\d{2})',
            ],
            'slfr': [
                r'SLFR.*?([0-9]+\.\d{2})',
                r'Standing\s*Lending\s*Facility\s*Rate.*?([0-9]+\.\d{2})',
            ],
            'opr': [
                r'OPR.*?([0-9]+\.\d{2})',
                r'Overnight\s*Policy\s*Rate.*?([0-9]+\.\d{2})',
            ],
        }

        for rate_type, pat_list in patterns.items():
            for pat in pat_list:
                m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
                if m:
                    try:
                        val = Decimal(m.group(1))
                        MarketRate.objects.update_or_create(
                            country=country,
                            rate_date=today,
                            rate_type=rate_type,
                            currency='',
                            defaults={'rate': val, 'source': 'CBSL'}
                        )
                        count += 1
                        break
                    except (InvalidOperation, ValueError):
                        continue

        return count


class SeylanBankRateScraper(BaseScraper):
    """Scrape Seylan Bank exchange rates."""
    SOURCE_NAME = "Seylan Bank"
    BASE_URL = "https://www.seylan.lk/exchange-rates"

    def scrape(self):
        country = Country.objects.get(code='LKA')
        resp = requests.get(self.BASE_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # Parse table rows for exchange rates
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.find_all('tr')

        count = 0
        today = date.today()
        currencies = ['USD', 'GBP', 'EUR', 'JPY', 'AUD', 'CAD', 'SGD']

        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 6:
                continue
            text = cells[0].get_text(strip=True)
            for curr in currencies:
                if curr in text:
                    try:
                        buying = Decimal(cells[2].get_text(strip=True).replace(',', ''))
                        selling = Decimal(cells[3].get_text(strip=True).replace(',', ''))
                        tt_buy = Decimal(cells[4].get_text(strip=True).replace(',', ''))
                        tt_sell = Decimal(cells[5].get_text(strip=True).replace(',', ''))

                        BankExchangeRate.objects.update_or_create(
                            country=country,
                            bank_name='Seylan Bank',
                            rate_date=today,
                            currency=curr,
                            defaults={
                                'buying_rate': buying,
                                'selling_rate': selling,
                                'tt_buying_rate': tt_buy,
                                'tt_selling_rate': tt_sell,
                                'source_url': self.BASE_URL,
                            }
                        )
                        count += 1
                    except (InvalidOperation, IndexError):
                        continue
                    break

        self.items_scraped = count
        self.status = 'success' if count > 0 else 'failed'


class NDBBankRateScraper(BaseScraper):
    """Scrape National Development Bank (NDB) exchange rates."""
    SOURCE_NAME = "NDB Bank"
    BASE_URL = "https://www.ndbbank.com/rates/exchange-rates"

    def scrape(self):
        country = Country.objects.get(code='LKA')
        resp = requests.get(self.BASE_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        resp.raise_for_status()
        html = resp.text

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        count = 0
        today = date.today()
        # Map full names to currency codes
        currency_map = {
            'US Dollar': 'USD',
            'British Pound': 'GBP',
            'Euro': 'EUR',
            'Japanese Yen': 'JPY',
            'Australian Dollars': 'AUD',
            'Canadian Dollars': 'CAD',
            'Singapore Dollar': 'SGD',
        }

        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 8:
                    continue
                text = cells[0].get_text(strip=True)
                for name, curr in currency_map.items():
                    if name in text:
                        try:
                            # Columns: Currency | Code | CurrBuy | CurrSell | DDBuy | DDSell | TTBuy | TTSell
                            buying = Decimal(cells[6].get_text(strip=True).replace(',', ''))
                            selling = Decimal(cells[7].get_text(strip=True).replace(',', ''))
                            BankExchangeRate.objects.update_or_create(
                                country=country,
                                bank_name='NDB Bank',
                                rate_date=today,
                                currency=curr,
                                defaults={
                                    'buying_rate': buying,
                                    'selling_rate': selling,
                                    'source_url': self.BASE_URL,
                                }
                            )
                            count += 1
                        except (InvalidOperation, IndexError, ValueError):
                            continue
                        break

        self.items_scraped = count
        self.status = 'success' if count > 0 else 'failed'


class CommercialBankRateScraper(BaseScraper):
    """Scrape Commercial Bank exchange rates."""
    SOURCE_NAME = "Commercial Bank"
    BASE_URL = "https://www.combank.lk/rates-tariff"

    def scrape(self):
        country = Country.objects.get(code='LKA')
        resp = requests.get(self.BASE_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        resp.raise_for_status()
        html = resp.text

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        count = 0
        today = date.today()
        currencies = ['USD', 'GBP', 'EUR', 'JPY', 'AUD', 'CAD']

        # Find exchange rate table
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                text = cells[0].get_text(strip=True)
                for curr in currencies:
                    if curr in text:
                        try:
                            buying = Decimal(cells[1].get_text(strip=True).replace(',', ''))
                            selling = Decimal(cells[2].get_text(strip=True).replace(',', ''))
                            BankExchangeRate.objects.update_or_create(
                                country=country,
                                bank_name='Commercial Bank',
                                rate_date=today,
                                currency=curr,
                                defaults={
                                    'buying_rate': buying,
                                    'selling_rate': selling,
                                    'source_url': self.BASE_URL,
                                }
                            )
                            count += 1
                        except (InvalidOperation, IndexError):
                            continue
                        break

        self.items_scraped = count
        self.status = 'success' if count > 0 else 'failed'


class SampathBankRateScraper(BaseScraper):
    """Scrape Sampath Bank exchange rates."""
    SOURCE_NAME = "Sampath Bank"
    BASE_URL = "https://www.sampath.lk/rates-and-charges?activeTab=exchange-rates"

    def scrape(self):
        country = Country.objects.get(code='LKA')
        resp = requests.get(self.BASE_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        resp.raise_for_status()
        html = resp.text

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        count = 0
        today = date.today()
        currencies = ['USD', 'GBP', 'EUR', 'JPY', 'AUD', 'CAD', 'SGD']

        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue
                text = cells[0].get_text(strip=True)
                for curr in currencies:
                    if curr in text:
                        try:
                            buying = Decimal(cells[1].get_text(strip=True).replace(',', ''))
                            selling = Decimal(cells[2].get_text(strip=True).replace(',', ''))
                            BankExchangeRate.objects.update_or_create(
                                country=country,
                                bank_name='Sampath Bank',
                                rate_date=today,
                                currency=curr,
                                defaults={
                                    'buying_rate': buying,
                                    'selling_rate': selling,
                                    'source_url': self.BASE_URL,
                                }
                            )
                            count += 1
                        except (InvalidOperation, IndexError):
                            continue
                        break

        self.items_scraped = count
        self.status = 'success' if count > 0 else 'failed'


class USTreasuryYieldScraper(BaseScraper):
    """Fetch the latest US Treasury 10-year yield from treasury.gov XML feed."""
    SOURCE_NAME = "US Treasury"
    BASE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    TENOR = "BC_10YEAR"
    RATE_TYPE = "us_treasury_10y"

    def scrape(self):
        country = Country.objects.get(code='LKA')
        year = date.today().year
        url = f"{self.BASE_URL}?data=daily_treasury_yield_curve&field_tdr_date_value={year}"

        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices',
        }
        entries = root.findall('atom:entry', ns)
        if not entries:
            raise ValueError(f"No Treasury yield entries returned for {year}")

        latest = max(entries, key=lambda e: e.find('.//d:NEW_DATE', ns).text)
        date_text = latest.find('.//d:NEW_DATE', ns).text[:10]
        rate_date = datetime.strptime(date_text, '%Y-%m-%d').date()

        val_node = latest.find(f'.//d:{self.TENOR}', ns)
        if val_node is None or val_node.text is None:
            raise ValueError(f"{self.TENOR} value missing in latest Treasury entry")
        rate = Decimal(val_node.text)

        MarketRate.objects.update_or_create(
            country=country,
            rate_date=rate_date,
            rate_type=self.RATE_TYPE,
            currency='USD',
            defaults={'rate': rate, 'source': self.SOURCE_NAME},
        )

        self.items_scraped = 1
        self.status = 'success'

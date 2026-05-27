"""
Scrapers for Sri Lankan market data:
- CBSL indicative exchange rates
- CBSL interest rates (AWPLR, TBill, SDFR, SLFR, OPR)
- Commercial bank exchange rates
"""

import re
import requests
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
        results = {'exchange_rate': 0, 'interest_rates': 0}

        # 1. Daily indicative exchange rate
        try:
            self._scrape_exchange_rate(country)
            results['exchange_rate'] = 1
        except Exception as e:
            self.errors.append(f"Exchange rate scrape failed: {e}")

        # 2. Interest rates from CBSL rates page
        try:
            count = self._scrape_interest_rates(country)
            results['interest_rates'] = count
        except Exception as e:
            self.errors.append(f"Interest rate scrape failed: {e}")

        self.items_scraped = sum(results.values())
        self.status = 'success' if self.items_scraped > 0 else 'failed'

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

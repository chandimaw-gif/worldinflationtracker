"""
Central Bank of Sri Lanka (CBSL) scraper.

Targets:
- USD/LKR exchange rate (daily) — via open.er-api.com (free, reliable)
- Gold price (daily) — via gold-api.com + exchange rate conversion
"""

import json
import re
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date

from scrapers.base import BaseScraper


class CBSLExchangeRateScraper(BaseScraper):
    """
    Scrape USD/LKR exchange rate.
    Uses open.er-api.com as a reliable free source.
    """

    SOURCE_NAME = "CBSL"
    BASE_URL = "https://open.er-api.com"
    RATE_LIMIT_SECONDS = 1.0

    def scrape(self):
        today = date.today()

        try:
            resp = self.fetch('/v6/latest/USD')
            data = resp.json()
        except Exception as e:
            self.log_error(f"Failed to fetch exchange rate from API: {e}")
            self.items_failed += 1
            return

        lkr_rate = data.get('rates', {}).get('LKR')
        if not lkr_rate:
            self.log_error("LKR rate not found in API response")
            self.items_failed += 1
            return

        rate = Decimal(str(lkr_rate)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

        self.save_exchange_rate(
            rate_date=today,
            rate=rate,
            base_currency='USD',
            local_currency='LKR',
            source='open.er-api.com (CBSL referenced)',
        )


class CBSLGoldScraper(BaseScraper):
    """
    Scrape gold price in LKR per gram.
    
    Strategy:
    1. Get USD/LKR exchange rate from open.er-api.com
    2. Get gold price in USD per troy ounce from gold-api.com
    3. Convert: LKR/gram = (USD/oz × LKR/USD) / 31.1035
    
    22-carat gold is ~91.6% pure, so we also apply purity factor.
    """

    SOURCE_NAME = "CBSL_Gold"
    BASE_URL = "https://api.gold-api.com"
    RATE_LIMIT_SECONDS = 1.0

    TROY_OUNCE_TO_GRAM = Decimal('31.1034768')
    CARAT_22_PURITY = Decimal('0.9167')  # 22/24

    def scrape(self):
        from core.models import BasketItem

        today = date.today()

        # Fetch exchange rate
        try:
            fx_resp = self.session.get('https://open.er-api.com/v6/latest/USD', timeout=10)
            fx_resp.raise_for_status()
            fx_data = fx_resp.json()
            lkr_rate = Decimal(str(fx_data['rates']['LKR']))
        except Exception as e:
            self.log_error(f"Failed to fetch exchange rate for gold calc: {e}")
            self.items_failed += 1
            return

        # Fetch gold price in USD per troy ounce
        try:
            gold_resp = self.fetch('/price/XAU')
            gold_data = gold_resp.json()
            usd_per_oz = Decimal(str(gold_data['price']))
        except Exception as e:
            self.log_error(f"Failed to fetch gold price from API: {e}")
            self.items_failed += 1
            return

        # Calculate LKR per gram of 22-carat gold
        # LKR/gram = (USD/oz × LKR/USD) / grams_per_oz × purity
        lkr_per_gram_24k = (usd_per_oz * lkr_rate) / self.TROY_OUNCE_TO_GRAM
        lkr_per_gram_22k = lkr_per_gram_24k * self.CARAT_22_PURITY
        lkr_per_gram_22k = lkr_per_gram_22k.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

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
                price=lkr_per_gram_22k,
                observation_date=today,
                source_url='https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates',
                source_name='CBSL Gold (calculated from spot)',
                raw_data={
                    'usd_per_oz': str(usd_per_oz),
                    'lkr_rate': str(lkr_rate),
                    'purity_22k': str(self.CARAT_22_PURITY),
                    'method': 'XAU_USD * USD_LKR / 31.1035 * 0.9167',
                },
            )
        else:
            self.log_error("Gold basket item not found")
            self.items_failed += 1

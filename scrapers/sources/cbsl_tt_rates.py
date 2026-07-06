"""
CBSL TT (Telegraphic Transfer) Exchange Rate Scraper.

Fetches the average buying and selling TT rates published daily by CBSL.
These are the average of quotes from selected licensed banks at 9:30 AM.

Source: https://www.cbsl.gov.lk/cbsl_custom/exratestt/exratestt.php

Currencies tracked: USD, GBP, EUR, AUD, CAD, SGD, JPY, INR
"""

import re
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup

from core.models import BankExchangeRate, Country

logger = logging.getLogger('scrapers')

CBSL_TT_URL = 'https://www.cbsl.gov.lk/cbsl_custom/exratestt/exratestt.php'
CBSL_INDICATIVE_URL = 'https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates.php'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-buy-and-sell-exchange-rates',
    'Accept': 'text/html,application/xhtml+xml,*/*',
}

CURRENCY_MAP = {
    'US Dollar': 'USD',
    'USD': 'USD',
    'Sterling Pound': 'GBP',
    'GBP': 'GBP',
    'Euro': 'EUR',
    'EUR': 'EUR',
    'Australian Dollar': 'AUD',
    'AUD': 'AUD',
    'Canadian Dollar': 'CAD',
    'CAD': 'CAD',
    'Singapore Dollar': 'SGD',
    'SGD': 'SGD',
    'Japanese Yen': 'JPY',
    'JPY': 'JPY',
    'Indian Rupee': 'INR',
    'INR': 'INR',
}

TARGET_CURRENCIES = ['USD', 'GBP', 'EUR', 'AUD', 'CAD', 'SGD']


def _parse_decimal(text: str):
    """Safely parse a decimal from text, return None if invalid."""
    if not text:
        return None
    clean = text.strip().replace(',', '').replace(' ', '')
    if not clean or clean == '-' or clean == 'N/A':
        return None
    try:
        val = Decimal(clean)
        return val if val > 0 else None
    except InvalidOperation:
        return None


def fetch_cbsl_tt_rates() -> list[dict]:
    """
    Fetch latest TT buy/sell rates from CBSL.
    Returns list of dicts: {currency, buying, selling, date}
    """
    try:
        # POST request for latest rates
        resp = requests.post(
            CBSL_TT_URL,
            headers=HEADERS,
            data={
                'curr': ','.join(TARGET_CURRENCIES),
                'datetype': 'latest',
                'Submit': 'Submit',
            },
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"CBSL TT rates fetch failed: {e}")
        # Fallback: try GET with no params (returns latest)
        try:
            resp = requests.get(CBSL_TT_URL, headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e2:
            logger.error(f"CBSL TT rates GET fallback also failed: {e2}")
            return []

    return _parse_tt_response(resp.text)


def _parse_tt_response(html: str) -> list[dict]:
    """Parse the CBSL TT rates HTML table."""
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Extract date from page if available
    rate_date = date.today()
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', html)
    if date_match:
        try:
            rate_date = datetime.strptime(date_match.group(1), '%Y-%m-%d').date()
        except ValueError:
            pass

    # Find the rates table
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                continue

            currency_text = cells[0].get_text(strip=True)

            # Identify currency
            currency = None
            for name, code in CURRENCY_MAP.items():
                if name.lower() in currency_text.lower() or currency_text.strip() == code:
                    currency = code
                    break

            if not currency or currency not in TARGET_CURRENCIES:
                continue

            # Try to extract buying and selling rates
            # Table format varies: Currency | Buying | Selling  or  Currency | Code | Buying | Selling
            buying = None
            selling = None

            if len(cells) >= 4:
                buying = _parse_decimal(cells[2].get_text(strip=True))
                selling = _parse_decimal(cells[3].get_text(strip=True))
            elif len(cells) >= 3:
                buying = _parse_decimal(cells[1].get_text(strip=True))
                selling = _parse_decimal(cells[2].get_text(strip=True))

            if buying or selling:
                results.append({
                    'currency': currency,
                    'buying': buying,
                    'selling': selling,
                    'date': rate_date,
                })

    # Fallback: regex extraction if table parsing failed
    if not results:
        results = _regex_extract_rates(html, rate_date)

    return results


def _regex_extract_rates(html: str, rate_date: date) -> list[dict]:
    """Regex fallback to extract rates from page text."""
    results = []
    text = BeautifulSoup(html, 'html.parser').get_text()

    for currency in TARGET_CURRENCIES:
        # Look for patterns like "USD ... 299.50 ... 302.75"
        pattern = rf'{currency}[^\d]{{1,30}}(\d{{2,3}}\.\d{{2,4}})[^\d]{{1,20}}(\d{{2,3}}\.\d{{2,4}})'
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            buying = _parse_decimal(m.group(1))
            selling = _parse_decimal(m.group(2))
            if buying and selling and buying < selling:
                results.append({
                    'currency': currency,
                    'buying': buying,
                    'selling': selling,
                    'date': rate_date,
                })

    return results


def save_cbsl_tt_rates(rates: list[dict], country) -> int:
    """Save CBSL TT rates as BankExchangeRate records under 'CBSL Average TT'."""
    saved = 0
    for r in rates:
        if not r.get('buying') and not r.get('selling'):
            continue
        try:
            BankExchangeRate.objects.update_or_create(
                country=country,
                bank_name='CBSL Average TT',
                rate_date=r['date'],
                currency=r['currency'],
                defaults={
                    'tt_buying_rate': r.get('buying'),
                    'tt_selling_rate': r.get('selling'),
                    'buying_rate': r.get('buying'),
                    'selling_rate': r.get('selling'),
                    'source_url': CBSL_TT_URL,
                }
            )
            saved += 1
        except Exception as e:
            logger.error(f"Failed to save {r['currency']} TT rate: {e}")

    return saved


def run_cbsl_tt_scraper() -> dict:
    """Main entry point — fetch and save CBSL TT rates."""
    try:
        country = Country.objects.get(code='LKA')
    except Country.DoesNotExist:
        return {'status': 'failed', 'error': 'Country LKA not found'}

    rates = fetch_cbsl_tt_rates()

    if not rates:
        return {
            'status': 'failed',
            'error': 'No rates parsed from CBSL TT page',
            'items_scraped': 0,
        }

    saved = save_cbsl_tt_rates(rates, country)

    return {
        'status': 'success',
        'items_scraped': saved,
        'currencies': [r['currency'] for r in rates],
        'date': str(rates[0]['date']) if rates else None,
    }

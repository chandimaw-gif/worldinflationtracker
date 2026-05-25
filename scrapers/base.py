"""
Base scraper class for World Inflation Tracker.

Provides:
- HTTP session with retries, timeouts, and realistic headers
- Structured logging to Django models (ScrapeLog, PriceObservation, PriceAuditLog)
- Error handling and graceful degradation
- Rate limiting between requests
"""

import logging
import time
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from django.utils import timezone
from core.models import (
    Country, BasketItem, PriceObservation, PriceAuditLog,
    ScrapeLog, ExchangeRate
)

logger = logging.getLogger('scrapers')


class BaseScraper:
    """
    Abstract base class for all price scrapers.
    """

    SOURCE_NAME: str = ""
    BASE_URL: str = ""
    COUNTRY_CODE: str = "LKA"
    DEFAULT_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 1.0
    RATE_LIMIT_SECONDS: float = 1.5

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.0 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.0'
            ),
            'Accept': (
                'text/html,application/xhtml+xml,application/xml;'
                'q=0.9,image/avif,image/webp,*/*;q=0.8'
            ),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self._last_request_time: Optional[float] = None
        self.scrape_log: Optional[ScrapeLog] = None
        self.items_scraped = 0
        self.items_failed = 0
        self.errors: List[str] = []

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.RATE_LIMIT_SECONDS:
                time.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        self._last_request_time = time.time()

    def fetch(self, url: str, **kwargs) -> requests.Response:
        """Make a rate-limited GET request."""
        self._rate_limit()
        full_url = urljoin(self.BASE_URL, url) if not url.startswith('http') else url
        logger.info(f"[{self.SOURCE_NAME}] Fetching: {full_url}")
        response = self.session.get(
            full_url,
            timeout=kwargs.get('timeout', self.DEFAULT_TIMEOUT),
            **{k: v for k, v in kwargs.items() if k != 'timeout'}
        )
        response.raise_for_status()
        return response

    def fetch_soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch and parse HTML with BeautifulSoup."""
        resp = self.fetch(url, **kwargs)
        # Force UTF-8 encoding; if that fails, use raw bytes
        try:
            resp.encoding = 'utf-8'
            return BeautifulSoup(resp.text, 'html.parser')
        except Exception:
            return BeautifulSoup(resp.content, 'html.parser')

    def start_scrape_log(self, job_name: str):
        """Create a ScrapeLog entry for this run."""
        country = Country.objects.filter(code=self.COUNTRY_CODE).first()
        self.scrape_log = ScrapeLog.objects.create(
            job_name=job_name,
            country=country,
            started_at=timezone.now(),
            status='running',
            source_url=self.BASE_URL,
        )
        self.items_scraped = 0
        self.items_failed = 0
        self.errors = []

    def finish_scrape_log(self, status: str = 'success'):
        """Update the ScrapeLog with results."""
        if self.scrape_log:
            self.scrape_log.completed_at = timezone.now()
            self.scrape_log.status = status
            self.scrape_log.items_scraped = self.items_scraped
            self.scrape_log.items_failed = self.items_failed
            self.scrape_log.error_log = '\n'.join(self.errors) if self.errors else ''
            self.scrape_log.save()

    def log_error(self, message: str):
        """Log an error message."""
        logger.error(f"[{self.SOURCE_NAME}] {message}")
        self.errors.append(message)

    def parse_price(self, text: str) -> Optional[Decimal]:
        """
        Extract a numeric price from text.
        Handles formats like:
          Rs. 450.00
          LKR 1,250.50
          450.00
          ₹450
        """
        if not text:
            return None
        # Remove currency symbols and words
        cleaned = re.sub(r'[RsLKR₹$€£\s,]', '', text.strip())
        # Extract first number-like sequence
        match = re.search(r'\d+\.?\d*', cleaned)
        if match:
            try:
                return Decimal(match.group())
            except InvalidOperation:
                pass
        return None

    def save_price(
        self,
        item: BasketItem,
        price: Decimal,
        observation_date: date,
        source_url: str,
        source_name: str = "",
        scrape_method: str = 'automated',
        raw_data: Optional[Dict] = None,
        product_page_title: str = "",
        product_page_snapshot: Optional[Dict] = None,
    ) -> PriceObservation:
        """
        Save a PriceObservation and corresponding PriceAuditLog.
        """
        country = item.country
        source_name = source_name or self.SOURCE_NAME

        # Create or update PriceObservation
        obs, created = PriceObservation.objects.update_or_create(
            item=item,
            country=country,
            observation_date=observation_date,
            defaults={
                'price': price,
                'currency_code': country.currency_code,
                'source_url': source_url,
                'source_name': source_name,
                'scrape_method': scrape_method,
                'raw_data': raw_data or {},
                'is_validated': False,
            }
        )

        # Always create an audit log entry
        PriceAuditLog.objects.create(
            item=item,
            country=country,
            observation_date=observation_date,
            price=price,
            source_url=source_url,
            source_name=source_name,
            scrape_method=scrape_method,
            product_page_title=product_page_title,
            product_page_snapshot=product_page_snapshot or {},
        )

        action = "Created" if created else "Updated"
        logger.info(
            f"[{self.SOURCE_NAME}] {action} PriceObservation: "
            f"{item.name} @ {price} on {observation_date}"
        )
        self.items_scraped += 1
        return obs

    def save_exchange_rate(
        self,
        rate_date: date,
        rate: Decimal,
        base_currency: str = 'USD',
        local_currency: str = 'LKR',
        source: str = "",
    ) -> ExchangeRate:
        """Save an exchange rate observation."""
        country = Country.objects.filter(code=self.COUNTRY_CODE).first()
        if not country:
            raise ValueError(f"Country {self.COUNTRY_CODE} not found")

        er, created = ExchangeRate.objects.update_or_create(
            country=country,
            rate_date=rate_date,
            base_currency=base_currency,
            defaults={
                'local_currency': local_currency,
                'rate': rate,
                'source': source or self.SOURCE_NAME,
            }
        )
        action = "Created" if created else "Updated"
        logger.info(
            f"[{self.SOURCE_NAME}] {action} ExchangeRate: "
            f"{base_currency}/{local_currency} @ {rate} on {rate_date}"
        )
        self.items_scraped += 1
        return er

    def scrape(self):
        """
        Main entry point. Subclasses MUST override this.
        """
        raise NotImplementedError("Subclasses must implement scrape()")

    def run(self, job_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the scraper with full logging and error handling.
        Returns a summary dict.
        """
        job_name = job_name or f"{self.SOURCE_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_scrape_log(job_name)
        status = 'success'

        try:
            self.scrape()
            if self.items_failed > 0 and self.items_scraped == 0:
                status = 'failed'
            elif self.items_failed > 0:
                status = 'partial'
        except Exception as e:
            self.log_error(f"Fatal error: {str(e)}")
            status = 'failed'
            logger.exception(f"[{self.SOURCE_NAME}] Scraping failed")
        finally:
            self.finish_scrape_log(status)

        return {
            'source': self.SOURCE_NAME,
            'status': status,
            'items_scraped': self.items_scraped,
            'items_failed': self.items_failed,
            'errors': self.errors,
            'scrape_log_id': self.scrape_log.id if self.scrape_log else None,
        }

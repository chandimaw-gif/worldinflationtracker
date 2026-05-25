"""
Celery tasks for scheduled price scraping.

Schedule overview:
- Daily:   Food prices (Keells, Spar), fuel (CEYPETCO), gas (Litro, Laugfs), exchange rates (CBSL)
- Weekly:  Electronics (Singer), clothing (NoLimit), telecom (Dialog)
- Monthly: Utilities (CEB, SLT), some household items
- Ad-hoc:  Manual entry fallback
"""

import logging
from celery import shared_task

from scrapers.base import BaseScraper
from scrapers.sources.cbsl import CBSLExchangeRateScraper, CBSLGoldScraper
from scrapers.sources.ceypetco import CEYPETCOScraper
from scrapers.sources.utilities import (
    CEBTariffScraper, LitroGasScraper, LaugfsGasScraper,
    DialogScraper, SLTScraper
)
from scrapers.sources.keells import KeellsScraper
from scrapers.sources.spar import SparScraper
from scrapers.sources.singer import SingerScraper
from scrapers.sources.fallback import ManualEntryScraper

logger = logging.getLogger('scrapers')


# ---------------------------------------------------------------------------
# Daily tasks
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_food_prices(self):
    """
    Scrape daily food prices from Keells and Spar.
    Runs every morning at 6:00 AM.
    """
    logger.info("Starting daily food price scraping...")
    results = []

    for scraper_class in [KeellsScraper, SparScraper]:
        try:
            scraper = scraper_class()
            result = scraper.run()
            results.append(result)
            logger.info(f"{scraper_class.__name__}: {result['status']} — "
                       f"{result['items_scraped']} scraped, {result['items_failed']} failed")
        except Exception as exc:
            logger.exception(f"{scraper_class.__name__} failed")
            results.append({'source': scraper_class.SOURCE_NAME, 'status': 'failed', 'error': str(exc)})
            raise self.retry(exc=exc)

    return {
        'task': 'scrape_food_prices',
        'results': results,
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_fuel_prices(self):
    """
    Check daily for fuel price revisions on CEYPETCO.
    Runs every morning at 5:00 AM.
    """
    logger.info("Checking CEYPETCO for fuel price updates...")
    try:
        scraper = CEYPETCOScraper()
        result = scraper.run()
        logger.info(f"CEYPETCO: {result['status']} — "
                   f"{result['items_scraped']} scraped, {result['items_failed']} failed")
        return {'task': 'check_fuel_prices', 'result': result}
    except Exception as exc:
        logger.exception("CEYPETCO scraper failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_gas_prices(self):
    """
    Check daily for LP gas price revisions.
    Runs every morning at 5:30 AM.
    """
    logger.info("Checking gas prices...")
    results = []

    for scraper_class in [LitroGasScraper, LaugfsGasScraper]:
        try:
            scraper = scraper_class()
            result = scraper.run()
            results.append(result)
            logger.info(f"{scraper_class.__name__}: {result['status']}")
        except Exception as exc:
            logger.exception(f"{scraper_class.__name__} failed")
            results.append({'source': scraper_class.SOURCE_NAME, 'status': 'failed', 'error': str(exc)})

    return {'task': 'check_gas_prices', 'results': results}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_exchange_rates(self):
    """
    Scrape daily USD/LKR exchange rate from CBSL.
    Runs every morning at 4:00 AM.
    """
    logger.info("Scraping CBSL exchange rates...")
    try:
        scraper = CBSLExchangeRateScraper()
        result = scraper.run()
        logger.info(f"CBSL Exchange Rate: {result['status']}")
        return {'task': 'scrape_exchange_rates', 'result': result}
    except Exception as exc:
        logger.exception("CBSL exchange rate scraper failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_gold_price(self):
    """
    Scrape daily gold price from CBSL.
    Runs every morning at 4:30 AM.
    """
    logger.info("Scraping CBSL gold price...")
    try:
        scraper = CBSLGoldScraper()
        result = scraper.run()
        logger.info(f"CBSL Gold: {result['status']}")
        return {'task': 'scrape_gold_price', 'result': result}
    except Exception as exc:
        logger.exception("CBSL gold scraper failed")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Weekly tasks (Mondays)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def scrape_electronics_prices(self):
    """
    Scrape weekly electronics prices from Singer.
    Runs every Monday at 7:00 AM.
    """
    logger.info("Starting weekly electronics price scraping...")
    try:
        scraper = SingerScraper()
        result = scraper.run()
        logger.info(f"Singer: {result['status']} — "
                   f"{result['items_scraped']} scraped, {result['items_failed']} failed")
        return {'task': 'scrape_electronics_prices', 'result': result}
    except Exception as exc:
        logger.exception("Singer scraper failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def scrape_telecom_prices(self):
    """
    Scrape weekly telecom prices from Dialog.
    Runs every Monday at 7:30 AM.
    """
    logger.info("Checking Dialog for telecom price updates...")
    try:
        scraper = DialogScraper()
        result = scraper.run()
        logger.info(f"Dialog: {result['status']}")
        return {'task': 'scrape_telecom_prices', 'result': result}
    except Exception as exc:
        logger.exception("Dialog scraper failed")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Monthly tasks (1st of month)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def scrape_utility_prices(self):
    """
    Scrape monthly utility prices (CEB electricity, SLT broadband).
    Runs on the 1st of every month at 8:00 AM.
    """
    logger.info("Starting monthly utility price scraping...")
    results = []

    for scraper_class in [CEBTariffScraper, SLTScraper]:
        try:
            scraper = scraper_class()
            result = scraper.run()
            results.append(result)
            logger.info(f"{scraper_class.__name__}: {result['status']}")
        except Exception as exc:
            logger.exception(f"{scraper_class.__name__} failed")
            results.append({'source': scraper_class.SOURCE_NAME, 'status': 'failed', 'error': str(exc)})

    return {'task': 'scrape_utility_prices', 'results': results}


# ---------------------------------------------------------------------------
# News feeds (every 30 minutes)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def fetch_news_feeds(self):
    """
    Fetch RSS feeds every 30 minutes.
    Placeholder — implement with feedparser for specific Sri Lankan news sources.
    """
    logger.info("Fetching news RSS feeds...")
    # TODO: Implement RSS feed parsing for:
    # - DailyMirror (economy)
    # - The Sunday Times (business)
    # - EconomyNext
    # - Ada Derana (business)
    return "News feed fetching not yet implemented."


# ---------------------------------------------------------------------------
# Ad-hoc / utility tasks
# ---------------------------------------------------------------------------

@shared_task
def run_manual_entry_scraper(json_path: str = None):
    """
    Run the manual entry scraper to load prices from a JSON file.
    """
    logger.info("Running manual entry scraper...")
    scraper = ManualEntryScraper(json_path=json_path)
    return scraper.run()


@shared_task
def run_all_scrapers():
    """
    Run all scrapers sequentially. Useful for initial data seeding.
    """
    logger.info("Running all scrapers...")
    all_results = []

    scrapers = [
        CBSLExchangeRateScraper,
        CBSLGoldScraper,
        CEYPETCOScraper,
        LitroGasScraper,
        LaugfsGasScraper,
        CEBTariffScraper,
        SLTScraper,
        DialogScraper,
        KeellsScraper,
        SparScraper,
        SingerScraper,
    ]

    for scraper_class in scrapers:
        try:
            scraper = scraper_class()
            result = scraper.run()
            all_results.append(result)
        except Exception as exc:
            logger.exception(f"{scraper_class.__name__} failed")
            all_results.append({
                'source': scraper_class.SOURCE_NAME,
                'status': 'failed',
                'error': str(exc),
            })

    return {
        'task': 'run_all_scrapers',
        'results': all_results,
        'total_scraped': sum(r.get('items_scraped', 0) for r in all_results),
        'total_failed': sum(r.get('items_failed', 0) for r in all_results),
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def download_cbsl_price_report(self):
    """
    Download the latest CBSL Daily Price Report PDF.
    Runs every Monday at 9:00 AM.
    """
    import subprocess
    from django.conf import settings

    report_dir = os.path.join(settings.BASE_DIR, 'data', 'cbsl_reports')
    os.makedirs(report_dir, exist_ok=True)

    try:
        result = subprocess.run(
            ['python3', 'manage.py', 'download_cbsl_report'],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        logger.info(f"CBSL report download: {result.stdout}")
        return result.stdout
    except Exception as exc:
        logger.exception("CBSL report download failed")
        raise self.retry(exc=exc)

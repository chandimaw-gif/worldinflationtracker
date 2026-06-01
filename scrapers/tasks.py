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
def import_exchange_rates_from_sheet(self):
    """
    Daily at 10:30 AM SLT (05:00 UTC): import bank exchange rates
    from the WIT Google Sheet Exchange Rates tab.
    Runs 30 minutes after the Apps Script updates rates at 10:00 AM.
    """
    logger.info("Importing bank exchange rates from Google Sheet...")
    try:
        from django.core.management import call_command
        call_command('import_google_sheet_rates')
        return {'task': 'import_exchange_rates_from_sheet', 'status': 'success'}
    except Exception as exc:
        logger.exception("Exchange rate import failed")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def import_wit_prices_from_sheet(self):
    """
    1st of each month at 12:30 PM SLT (07:00 UTC): import WIT prices
    from the Google Sheet and recompute WIT CPI.
    Runs 30 minutes after Apps Script updates prices at 12:00 noon.
    """
    logger.info("Importing WIT prices from Google Sheet...")
    try:
        from django.core.management import call_command
        call_command('import_wit_prices')
        return {'task': 'import_wit_prices_from_sheet', 'status': 'success'}
    except Exception as exc:
        logger.exception("WIT price import failed")
        raise self.retry(exc=exc)



    """
    Fetch CBSL daily average TT buying/selling exchange rates.
    Runs every morning at 10:00 AM (after 9:30 AM bank quotes).
    """
    logger.info("Fetching CBSL TT exchange rates...")
    try:
        from scrapers.sources.cbsl_tt_rates import run_cbsl_tt_scraper
        result = run_cbsl_tt_scraper()
        logger.info(f"CBSL TT rates: {result['status']} — {result.get('items_scraped', 0)} saved")
        return {'task': 'scrape_cbsl_tt_rates', 'result': result}
    except Exception as exc:
        logger.exception("CBSL TT rates scraper failed")
        raise self.retry(exc=exc)



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
    Sources: EconomyNext, Ada Derana, NewsFirst, Daily FT, Daily Mirror,
             The Morning, Colombo Gazette + CBSL press releases.
    Classifies articles by category and cleans HTML from summaries.
    """
    import feedparser
    import requests
    import html
    import re
    from core.models import NewsArticle, Country
    from datetime import datetime
    from django.utils import timezone

    logger.info("Fetching news RSS feeds...")

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        )
    }

    feeds = [
        # Primary sources — direct RSS
        ('https://economynext.com/feed/', 'EconomyNext', 'economy'),

        # Google News RSS — aggregates all Sri Lankan sources, very reliable
        ('https://news.google.com/rss/search?q=sri+lanka+inflation+ccpi+economy&hl=en-LK&gl=LK&ceid=LK:en',
         'Google News · Economy', 'economy'),
        ('https://news.google.com/rss/search?q=CBSL+central+bank+sri+lanka+policy+rate&hl=en-LK&gl=LK&ceid=LK:en',
         'Google News · CBSL', 'policy'),
        ('https://news.google.com/rss/search?q=sri+lanka+rupee+exchange+rate+LKR&hl=en-LK&gl=LK&ceid=LK:en',
         'Google News · Markets', 'markets'),
        ('https://news.google.com/rss/search?q=sri+lanka+fuel+price+food+price&hl=en-LK&gl=LK&ceid=LK:en',
         'Google News · Prices', 'economy'),

        # Direct sources — work from Cloudways IP
        ('https://www.adaderana.lk/rss.php', 'Ada Derana', 'economy'),
        ('https://www.dailymirror.lk/rss', 'Daily Mirror', 'economy'),
        ('https://colombogazette.com/feed', 'Colombo Gazette', 'policy'),
        ('https://www.newsfirst.lk/feed', 'NewsFirst', 'economy'),
    ]

    # Keywords for category classification
    CATEGORY_KEYWORDS = {
        'policy': ['cbsl', 'central bank', 'policy rate', 'monetary', 'government', 'ministry',
                   'parliament', 'president', 'imf', 'budget', 'fiscal', 'tax', 'regulation'],
        'markets': ['exchange rate', 'usd', 'lkr', 'rupee', 'stock', 'cse', 'shares', 'bond',
                    'forex', 'gold price', 'oil price', 'interest rate', 'treasury'],
        'international': ['global', 'world', 'china', 'india', 'usa', 'fed', 'ecb', 'opec',
                          'international', 'export', 'import', 'trade'],
        'economy': ['inflation', 'cpi', 'ccpi', 'price', 'cost', 'gdp', 'growth', 'economy',
                    'fuel', 'food', 'electricity', 'gas', 'transport', 'employment'],
    }

    def classify_category(title, summary, default_cat):
        text = (title + ' ' + summary).lower()
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return cat
        return default_cat

    def clean_summary(text):
        """Strip HTML tags and clean up RSS summaries."""
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        # Truncate to ~280 chars at sentence boundary
        if len(text) > 280:
            truncated = text[:280]
            last_period = truncated.rfind('.')
            if last_period > 150:
                text = truncated[:last_period + 1]
            else:
                text = truncated.rstrip() + '…'
        return text

    created_count = 0
    lka = Country.objects.filter(code='LKA').first()

    for url, source_name, default_category in feeds:
        try:
            # Fetch with real browser headers to avoid 403s
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200:
                logger.warning(f"{source_name}: HTTP {r.status_code}")
                continue

            parsed = feedparser.parse(r.text)
            if not parsed.entries:
                logger.warning(f"{source_name}: no entries found")
                continue

            for entry in parsed.entries[:10]:
                title = entry.get('title', '').strip()
                link = entry.get('link', '').strip()
                raw_summary = entry.get('summary', '') or entry.get('description', '')
                summary = clean_summary(raw_summary)
                published = entry.get('published_parsed') or entry.get('updated_parsed')

                if not title or not link:
                    continue

                # Skip non-economy articles from general news sources
                # (but not from Google News which is already search-filtered)
                if source_name in ('Ada Derana', 'NewsFirst', 'Daily Mirror', 'Colombo Gazette') and 'Google News' not in source_name:
                    econ_keywords = ['inflation', 'price', 'economy', 'cbsl', 'rupee', 'fuel',
                                     'food', 'cost', 'tax', 'budget', 'imf', 'trade', 'growth',
                                     'gdp', 'interest', 'exchange', 'bank', 'financial', 'market']
                    text_check = (title + ' ' + summary).lower()
                    if not any(kw in text_check for kw in econ_keywords):
                        continue

                # For Google News, extract the real publisher from the source field
                display_source = source_name
                if 'Google News' in source_name:
                    # Google News puts publisher in entry.source.title or at end of title
                    real_source = (entry.get('source') or {}).get('title', '')
                    if not real_source:
                        # Fall back: extract from title " - Publisher" suffix
                        match = re.search(r'\s+-\s+([\w\s\.]+)$', title)
                        if match:
                            real_source = match.group(1).strip()
                    if real_source:
                        display_source = real_source
                    # Clean publisher suffix from title
                    title = re.sub(r'\s+-\s+[\w\s\.]+$', '', title).strip()

                published_dt = None
                if published:
                    try:
                        published_dt = datetime(*published[:6], tzinfo=timezone.get_current_timezone())
                    except Exception:
                        pass

                category = classify_category(title, summary, default_category)

                obj, created = NewsArticle.objects.update_or_create(
                    source_url=link,
                    defaults={
                        'country': lka,
                        'title': title,
                        'summary': summary,
                        'source_name': display_source,
                        'published_at': published_dt,
                        'category': category,
                    }
                )
                if created:
                    created_count += 1

            logger.info(f"{source_name}: processed {len(parsed.entries)} entries")

        except Exception as exc:
            logger.exception(f"Failed to fetch {source_name} RSS")

    # Clean up old articles (keep last 200)
    try:
        from core.models import NewsArticle
        cutoff_ids = NewsArticle.objects.order_by('-published_at').values_list('id', flat=True)[200:]
        if cutoff_ids:
            NewsArticle.objects.filter(id__in=list(cutoff_ids)).delete()
    except Exception:
        pass

    logger.info(f"News fetch complete. Created {created_count} new articles.")
    return f"Created {created_count} new articles."


# ---------------------------------------------------------------------------
# Ad-hoc / utility tasks
# ---------------------------------------------------------------------------

@shared_task
def compute_monthly_cpi():
    """
    Compute CPI indices for the current month.
    Runs on the 2nd of every month to ensure all monthly prices are collected.
    """
    import subprocess
    from django.conf import settings

    logger.info("Computing monthly CPI...")
    try:
        result = subprocess.run(
            ['python3', 'manage.py', 'compute_cpi', '--country', 'LKA'],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        logger.info(f"CPI compute: {result.stdout}")
        return result.stdout
    except Exception as exc:
        logger.exception("CPI computation failed")
        return str(exc)


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

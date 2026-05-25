# This ensures Celery discovers tasks in this app
from .tasks import (
    scrape_food_prices,
    check_fuel_prices,
    check_gas_prices,
    scrape_exchange_rates,
    scrape_gold_price,
    scrape_electronics_prices,
    scrape_telecom_prices,
    scrape_utility_prices,
    fetch_news_feeds,
    run_manual_entry_scraper,
    run_all_scrapers,
)

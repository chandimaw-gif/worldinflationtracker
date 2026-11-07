# Project Memory — World Inflation Tracker

## SSH / Server

- SSH access is via key `wit_deploy_key` (ed25519).
- Public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINpil9gFhBdb6R8tOD46iz2BW1StYiVxG1JHbIcsr8Nk wit-deploy-key`
- Server: `master_pnjkjbpsxn@157.245.60.144`
- App path: `/home/master/applications/ctaaqxskeb/public_html`

## Port Restrictions

- **WIT runs on port `8000` only.**
- **Port `8001` is reserved for another app — never use it.**

## Current Focus

- Configurable server-side price scrapers with real sources: Keells (Playwright/JS), Spar 2U (Shopify JSON API), CEYPETCO (fuel table).
- Management command: `python manage.py scrape_configured_sources --country LKA`
- Celery task scheduled daily at 06:30 SLT.

## Deployment Notes

- Pull from GitHub `main`, install requirements, run migrations, restart Gunicorn on port `8000`.
- Install Playwright browsers with `python3 -m playwright install chromium` if needed for Keells.
- See `DEPLOY.md` and `crontab.txt` for full commands.

## Agent Protocol

- Always read `agents.md` and `memory.md` when a new context window starts.
- Append to these files; never overwrite.

## Deployment Status — 2026-07-06

- Server deploy completed.
- `scrape_configured_sources` is live and saved real prices:
  - Spar: chicken 1500, coconut oil 1310, dhal 332, eggs 57.50 (per egg), milk powder 1146 (400g eq), sugar 248, tea 580
  - CEYPETCO: auto diesel 382, petrol 92 414, petrol 95 495

## Blocker

- Keells scraper (Playwright) cannot start until system browser deps are installed on Cloudways.
- Command that would need to run (with sudo): `playwright install-deps chromium` or apt install the listed libs.

## Files Updated

- `agents.md` and `memory.md` now contain SSH key and port 8000 rules.
- `crontab.txt` and `DEPLOY.md` are in the repo.

## Admin UI Added — 2026-07-06

- Django admin customized with project branding and quick-links dashboard.
- Superuser `chandimaw@gmail.com` password `WIT123!@#` confirmed working.
- ScrapeSource scheduling fields added (day-of-week, day-of-month).
- YouTubeSource model added with default sources seeded.
- Admin can add/edit sources and trigger YouTube fetch from the UI.

## Election Chart Markers — 2026-05-20

- Added vertical dashed lines to the home-page CPI chart and the exchange-rate chart for the Sep 2024 (Presidential) and Nov 2024 (General) elections.
- Custom Chart.js plugin `electionLines` registered in `base.html`; annotations injected from `frontend/views.py` for LKA.
- Files changed: `frontend/views.py`, `frontend/templates/base.html`, `frontend/templates/frontend/home.html`, `frontend/templates/frontend/exchange_rates.html`.
- Deployed to server and Gunicorn restarted on port 8000; both `/` and `/exchange-rates/` return HTTP 200 with markers present.

## Updated Election / Crisis Chart Markers — 2026-05-20

- Marker labels now render as slanted vertical text alongside each vertical line, alternating left/right of the line to avoid overlap.
- Added two new Sri Lanka markers:
  - **Mar 2020** — Start of Covid
  - **Apr 2020** — Start of economic crisis
- CPI chart axis now extends continuously back to Mar 2020 and fills missing months with null values.
- Exchange-rate chart now includes the full available daily history back to Mar 2020 (with `maxTicksLimit: 12` on the x-axis).
- Marker constants live in `frontend/views.py` as `LKA_CHART_ANNOTATIONS` and are reused by both charts.
- Deployed and restarted Gunicorn on port 8000.

## Exchange-Rate Chart Fix — 2026-05-20

- Rebuilt the exchange-rate chart using actual records only (no daily null padding), with an `x` scale of type `linear` (days since 2020-01-01).
- This restores the USD/LKR trend line and still shows the four vertical markers (Mar 2020, Apr 2020, Sep 2024, Nov 2024) using numeric `value` positions.
- Updated the custom `electionLines` plugin to support both label-based markers (CPI chart) and numeric `value` markers (exchange chart).
- x-axis ticks now format day numbers back to `Mon YYYY` in the browser.
- Deployed and restarted Gunicorn on port 8000.

## US Treasury Yield Scraper — 2026-05-20

- Added `us_treasury_10y` to `MarketRate` choices and a `USTreasuryYieldScraper` in `scrapers/sources/market_data.py`.
- The scraper reads the treasury.gov XML feed for the current year and saves the latest 10-year yield.
- Registered the scraper in `fetch_market_data`, `run_scrapers`, and the exchange-rates view (`US 10Y Treasury Yield`).
- Fixed `CBSLMarketRateScraper` so it no longer attempts to scrape USD/LKR (it was saving an incorrect value).
- Removed an erroneous `ExchangeRate` record (9.30 LKR/USD) created by the old CBSL market scraper.
- Scheduled the US Treasury scraper daily at 07:00 UTC in `crontab.txt` and on the server.
- Live page now shows **US 10Y Treasury Yield: 4.55%** (as of 2026-07-07).

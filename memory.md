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

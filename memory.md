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

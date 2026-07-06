# Deployment Notes — Configurable Scrapers

## Latest changes pushed to GitHub

Main branch now includes:

- `core.ScrapeSource` model for admin-configurable price scraping.
- `python manage.py scrape_configured_sources` management command.
- Example sources seeded for **Spar 2U**, **CEYPETCO**, and **Keells**.
- Celery task `scrapers.tasks.scrape_configured_sources` scheduled daily at 06:30 SLT.

## Deploy to Cloudways

SSH into the server as `master_pnjkjbpsxn@157.245.60.144` and run:

```bash
cd /home/master/applications/ctaaqxskeb/public_html
git pull origin main

# Install new dependency (lxml)
python3 -m pip install --user -r requirements.txt

# Apply migrations
python3 manage.py migrate

# Restart Gunicorn
pkill -9 -f 'gunicorn.*worldinflationtracker.wsgi'
sleep 2
export PATH="$HOME/.local/bin:$PATH"
nohup gunicorn worldinflationtracker.wsgi:application \
  --bind 127.0.0.1:8000 --workers 2 --timeout 60 --daemon \
  --log-file /tmp/gunicorn_wit.log \
  --access-logfile /tmp/gunicorn_wit_access.log \
  --pid /tmp/gunicorn_wit.pid \
  > /tmp/gunicorn_wit_nohup.log 2>&1 &
```

## Playwright for Keells

Keells is a React SPA and requires a browser for scraping. If Playwright browsers are not already installed, run:

```bash
python3 -m playwright install chromium
```

Then test a Keells source with:

```bash
python3 manage.py scrape_configured_sources --source "Keells" --limit 1 --dry-run
```

## Test non-JS sources

```bash
# Dry-run all configured sources (Spar + CEYPETCO will work without a browser)
python3 manage.py scrape_configured_sources --country LKA --dry-run

# Run only CEYPETCO fuel prices
python3 manage.py scrape_configured_sources --source "CEYPETCO"

# Run only Spar sources
python3 manage.py scrape_configured_sources --source "Spar"
```

## Admin monitoring

Visit `/admin/core/scrapesource/` to see:

- Last scraped price
- Last status (success/failed)
- Last error message
- Edit URLs/selectors without changing code

## Crontab

See `crontab.txt` for the recommended Cloudways schedule.

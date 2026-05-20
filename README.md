# World Inflation Tracker

Independent inflation tracking for Sri Lanka (and eventually the world).

## Tech Stack

- **Backend:** Django 4.2, Django REST Framework
- **Database:** PostgreSQL 15+
- **Cache/Queue:** Redis + Celery
- **Frontend:** Django Templates + Chart.js
- **Scraping:** Scrapy, Playwright, BeautifulSoup4

## Quick Start (Local)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
cp .env.example .env
# Edit .env with your settings

# 4. Run migrations
python manage.py migrate

# 5. Load Sri Lanka fixture data
python manage.py loaddata core/fixtures/sri_lanka_basket.json

# 6. Create superuser
python manage.py createsuperuser

# 7. Run server
python manage.py runserver
```

## Deployment (Cloudways)

See deployment instructions provided separately.

## Project Structure

```
worldinflationtracker/
├── core/              # Models, admin, fixtures
├── scrapers/          # Celery tasks for web scraping
├── cpi_engine/        # CPI calculation logic
├── api/               # REST API endpoints
├── frontend/          # Templates, static files, views
└── worldinflationtracker/  # Django project config
```

## Disclaimer

This is an independent research tool. Inflation rates are NOT official government statistics.

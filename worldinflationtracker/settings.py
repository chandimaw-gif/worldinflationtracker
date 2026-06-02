import os
import environ
from pathlib import Path

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

BASE_DIR = Path(__file__).resolve().parent.parent

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')

DEBUG = env('DEBUG', default=False)

ALLOWED_HOSTS = env('ALLOWED_HOSTS', default=['worldinflationtracker.com', 'www.worldinflationtracker.com', 'localhost', '127.0.0.1'])
# Ensure custom domains are always included even if Cloudways overrides ALLOWED_HOSTS
for _host in ['worldinflationtracker.com', 'www.worldinflationtracker.com']:
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[
    'https://worldinflationtracker.com',
    'https://www.worldinflationtracker.com',
    'https://phpstack-1559249-6432512.cloudwaysapps.com',
])

USE_X_FORWARDED_HOST = env.bool('USE_X_FORWARDED_HOST', default=True)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_celery_beat',
    'django_filters',
    'core',
    'scrapers',
    'cpi_engine',
    'api',
    'frontend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'frontend.middleware.CacheControlMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'worldinflationtracker.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'frontend' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'frontend.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'worldinflationtracker.wsgi.application'

DATABASES = {
    'default': env.db(default='postgres://user:password@localhost:5432/worldinflationtracker')
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

CELERY_BROKER_URL = env('REDIS_URL', default='redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Colombo'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery Beat Schedule (can also be configured via Django admin)
CELERY_BEAT_SCHEDULE = {
    'scrape-food-prices-daily': {
        'task': 'scrapers.tasks.scrape_food_prices',
        'schedule': 'crontab(hour=6, minute=0)',
    },
    'check-fuel-prices-daily': {
        'task': 'scrapers.tasks.check_fuel_prices',
        'schedule': 'crontab(hour=5, minute=0)',
    },
    'check-gas-prices-daily': {
        'task': 'scrapers.tasks.check_gas_prices',
        'schedule': 'crontab(hour=5, minute=30)',
    },
    'scrape-exchange-rates-daily': {
        'task': 'scrapers.tasks.scrape_exchange_rates',
        'schedule': 'crontab(hour=4, minute=0)',
    },
    'scrape-gold-price-daily': {
        'task': 'scrapers.tasks.scrape_gold_price',
        'schedule': 'crontab(hour=4, minute=30)',
    },
    'scrape-electronics-weekly': {
        'task': 'scrapers.tasks.scrape_electronics_prices',
        'schedule': 'crontab(day_of_week=1, hour=7, minute=0)',
    },
    'scrape-telecom-weekly': {
        'task': 'scrapers.tasks.scrape_telecom_prices',
        'schedule': 'crontab(day_of_week=1, hour=7, minute=30)',
    },
    'scrape-utilities-monthly': {
        'task': 'scrapers.tasks.scrape_utility_prices',
        'schedule': 'crontab(day_of_month=1, hour=8, minute=0)',
    },
    'fetch-news-feeds': {
        'task': 'scrapers.tasks.fetch_news_feeds',
        'schedule': 1800.0,  # every 30 minutes
    },
    'download-cbsl-report-weekly': {
        'task': 'scrapers.tasks.download_cbsl_price_report',
        'schedule': 'crontab(day_of_week=1, hour=9, minute=0)',
    },
    'compute-monthly-cpi': {
        'task': 'scrapers.tasks.compute_monthly_cpi',
        'schedule': 'crontab(day_of_month=2, hour=3, minute=0)',
    },
    # Fetch YouTube videos daily at 11:00 AM SLT (05:30 UTC)
    'fetch-youtube-videos-daily': {
        'task': 'scrapers.tasks.fetch_youtube_videos_task',
        'schedule': 'crontab(hour=5, minute=30)',
    },
    # Google Sheet imports — run after Apps Script updates
    # Apps Script updates exchange rates at 10:00 AM SLT (04:30 UTC)
    # We import at 10:30 AM SLT (05:00 UTC) — 30 min buffer
    'import-exchange-rates-from-sheet': {
        'task': 'scrapers.tasks.import_exchange_rates_from_sheet',
        'schedule': 'crontab(hour=5, minute=0)',
    },
    # Apps Script updates prices on 1st of month at 12:00 noon SLT (06:30 UTC)
    # We import at 12:30 PM SLT (07:00 UTC) — 30 min buffer
    'import-wit-prices-from-sheet': {
        'task': 'scrapers.tasks.import_wit_prices_from_sheet',
        'schedule': 'crontab(day_of_month=1, hour=7, minute=0)',
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Colombo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'frontend' / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

CORS_ALLOWED_ORIGINS = [
    "https://worldinflationtracker.com",
    "https://www.worldinflationtracker.com",
    "http://localhost:8000",
]

# Google AdSense configuration
# Replace with your actual publisher ID after AdSense approval
GOOGLE_ADSENSE_PUBLISHER_ID = env('GOOGLE_ADSENSE_PUBLISHER_ID', default='pub-2187016535602304')
GOOGLE_ADSENSE_ENABLED = env.bool('GOOGLE_ADSENSE_ENABLED', default=True)

LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'scrapers': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
        'cpi_engine': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
    },
}

# Google Sheet CSV URLs
SHEET_BASE = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSE_6nH-_hbGILUwWNJ3R89MWgSRAwSPU0eYlABobvV8VvR2qbkiUVxCXoImuGHx29J_dIpRH3InXnb/pub'
EXCHANGE_RATES_SHEET_CSV_URL = SHEET_BASE + '?gid=314532917&single=true&output=csv'
PRICE_SHEET_CSV_URL = SHEET_BASE + '?gid=2029087421&single=true&output=csv'
NEWS_SHEET_CSV_URL = SHEET_BASE + '?gid=845580084&single=true&output=csv'
USD_LKR_SHEET_CSV_URL = SHEET_BASE + '?gid=31393083&single=true&output=csv'

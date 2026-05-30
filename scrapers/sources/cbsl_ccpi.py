"""
CBSL Official CCPI Scraper.

Fetches the official Colombo Consumer Price Index (CCPI, 2021=100)
from the Central Bank of Sri Lanka's monthly press release PDFs.

URL pattern:
  https://www.cbsl.gov.lk/sites/default/files/cbslweb_documents/press/pr/
  press_{YYYYMMDD}_inflation_in_{month}_{year}_ccpi_e.pdf

Strategy:
  Each PDF contains a data table with 13 months of CCPI history.
  We parse the table using regex on extracted text.
  We store official figures in CPIIndex with index_type='official_ccpi'
  and index_type='official_core_ccpi' — separate from WIT's own calculations.

Official data structure (from PDF table):
  Year | Month | CCPI | Core CCPI | MoM% | Core MoM% | YoY% | Core YoY%
"""

import re
import logging
from datetime import date, datetime
from decimal import Decimal

import requests

logger = logging.getLogger('scrapers')

# Month name → number mapping
MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}

# CBSL PDF URL pattern — the date in the URL is the release date (last working day of month)
# We try multiple possible release dates for each month
CBSL_PDF_BASE = (
    "https://www.cbsl.gov.lk/sites/default/files/cbslweb_documents/press/pr/"
    "press_{date}_inflation_in_{month}_{year}_ccpi_e.pdf"
)

# Known release dates (last working day of each month)
# Format: (year, month) → 'YYYYMMDD' of the press release date
KNOWN_RELEASE_DATES = {
    (2026, 5): '20260529',
    (2026, 4): '20260430',
    (2026, 3): '20260331',
    (2026, 2): '20260227',
    (2026, 1): '20260130',
    (2025, 12): '20251231',
    (2025, 11): '20251201',
    (2025, 10): '20251031',
    (2025, 9): '20250930',
    (2025, 8): '20250829',
    (2025, 7): '20250731',
    (2025, 6): '20250630',
    (2025, 5): '20250530',
    (2025, 4): '20250430',
    (2025, 3): '20250328',
    (2025, 2): '20250228',
    (2025, 1): '20250131',
    (2024, 12): '20241231',
    (2024, 11): '20241129',
    (2024, 10): '20241031',
    (2024, 9): '20240930',
    (2024, 8): '20240830',
    (2024, 7): '20240731',
    (2024, 6): '20240628',
    (2024, 5): '20240531',
    (2024, 4): '20240430',
    (2024, 3): '20240329',
    (2024, 2): '20240229',
    (2024, 1): '20240131',
    (2023, 12): '20231229',
    (2023, 11): '20231130',
    (2023, 10): '20231031',
    (2023, 9): '20230929',
    (2023, 8): '20230831',
    (2023, 7): '20230731',
    (2023, 6): '20230630',
    (2023, 5): '20230531',
    (2023, 4): '20230428',
    (2023, 3): '20230331',
    (2023, 2): '20230228',
    (2023, 1): '20230131',
    (2022, 12): '20221230',
    (2022, 11): '20221130',
    (2022, 10): '20221031',
    (2022, 9): '20220930',
    (2022, 8): '20220831',
    (2022, 7): '20220729',
    (2022, 6): '20220630',
    (2022, 5): '20220531',
    (2022, 4): '20220429',
    (2022, 3): '20220331',
    (2022, 2): '20220228',
    (2022, 1): '20220131',
}

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/pdf,*/*',
    'Referer': 'https://www.cbsl.gov.lk/en/measures-of-consumer-price-inflation',
}


def build_pdf_url(year: int, month: int) -> str | None:
    """Build the PDF URL for a given year/month."""
    release_date = KNOWN_RELEASE_DATES.get((year, month))
    if not release_date:
        return None
    month_name = list(MONTH_MAP.keys())[month - 1]
    return CBSL_PDF_BASE.format(
        date=release_date,
        month=month_name,
        year=year,
    )


def fetch_pdf_text(year: int, month: int) -> str | None:
    """
    Download a CBSL CCPI press release PDF and return its text content.
    Returns None if unavailable.
    """
    url = build_pdf_url(year, month)
    if not url:
        logger.warning(f"No known PDF URL for {year}-{month:02d}")
        return None

    try:
        import io
        import pdfplumber

        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"CBSL PDF {year}-{month:02d}: HTTP {resp.status_code}")
            return None

        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            text = '\n'.join(
                page.extract_text() or ''
                for page in pdf.pages
            )
        return text

    except Exception as e:
        logger.error(f"Failed to fetch/parse CBSL PDF {year}-{month:02d}: {e}")
        return None


def parse_ccpi_table(text: str) -> list[dict]:
    """
    Parse the 'Movement of the CCPI (2021=100)' table from PDF text.

    Returns a list of dicts with keys:
        year, month, ccpi, core_ccpi, mom_pct, core_mom_pct, yoy_pct, core_yoy_pct

    The table rows look like (from extracted text):
        2025 May 192.8 179.2 0.8 0.2 -0.7 1.2 -1.2 2.4
        (year month ccpi core_ccpi mom core_mom yoy core_yoy annual_avg annual_avg_core)
    """
    results = []

    # Match data rows: year(optional) month ccpi core_ccpi mom core_mom yoy core_yoy ...
    # Year may only appear on first row of each year
    row_pattern = re.compile(
        r'(?:(\d{4})\s+)?'           # optional year
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+'
        r'([\d.]+)\s+'               # CCPI index
        r'([\d.]+)\s+'               # Core CCPI index
        r'(-?[\d.]+)\s+'             # MoM %
        r'(-?[\d.]+)\s+'             # Core MoM %
        r'(-?[\d.]+)\s+'             # YoY %
        r'(-?[\d.]+)',               # Core YoY %
        re.IGNORECASE
    )

    current_year = None
    for match in row_pattern.finditer(text):
        yr, mo, ccpi, core, mom, core_mom, yoy, core_yoy = match.groups()
        if yr:
            current_year = int(yr)
        if current_year is None:
            continue

        month_num = MONTH_MAP.get(mo.lower())
        if not month_num:
            continue

        results.append({
            'year': current_year,
            'month': month_num,
            'ccpi': Decimal(ccpi),
            'core_ccpi': Decimal(core),
            'mom_pct': Decimal(mom),
            'core_mom_pct': Decimal(core_mom),
            'yoy_pct': Decimal(yoy),
            'core_yoy_pct': Decimal(core_yoy),
        })

    return results


def save_official_ccpi(records: list[dict], country, source_note: str = '') -> tuple[int, int]:
    """
    Save parsed CCPI records to the CPIIndex table.

    Uses index_type='official_ccpi' and 'official_core_ccpi' to keep
    official government data separate from WIT's own calculations.

    Returns (created_count, updated_count).
    """
    from core.models import CPIIndex

    created = 0
    updated = 0

    # Official base period for CCPI 2021=100 series
    base_period = date(2021, 1, 1)

    for rec in records:
        period_date = date(rec['year'], rec['month'], 1)

        for idx_type, val, yoy, mom in [
            ('official_ccpi', rec['ccpi'], rec['yoy_pct'], rec['mom_pct']),
            ('official_core_ccpi', rec['core_ccpi'], rec['core_yoy_pct'], rec['core_mom_pct']),
        ]:
            obj, was_created = CPIIndex.objects.update_or_create(
                country=country,
                period_date=period_date,
                index_type=idx_type,
                group=None,
                defaults={
                    'index_value': val,
                    'yoy_inflation': yoy,
                    'mom_inflation': mom,
                    'ma12_inflation': None,
                    'base_period': base_period,
                    'methodology_note': (
                        f"Official CBSL/DCS CCPI (2021=100). {source_note}"
                    ),
                }
            )

            if was_created:
                created += 1
            else:
                updated += 1

    return created, updated

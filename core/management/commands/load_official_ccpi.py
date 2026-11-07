"""
Management command: load_official_ccpi

Loads official CCPI (2021=100) figures, as published by CBSL/DCS, into CPIIndex.

Two inputs:
  * data/official_ccpi_cbsl.json - figures copied from CBSL press release PDFs.
  * --pdf FILE                   - a newly downloaded CBSL "Inflation in <month>
                                   - CCPI" press release, which is parsed and merged.

It only reports differences unless --apply is passed:

    python3 manage.py load_official_ccpi                     # report only
    python3 manage.py load_official_ccpi --apply             # add/correct rows
    python3 manage.py load_official_ccpi --pdf release.pdf --apply

Why this is not automatic: cbsl.gov.lk answers this server with HTTP 403, so each
month's release PDF has to be downloaded elsewhere and passed in with --pdf.
"""

import calendar
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import Country, CPIIndex

MONTHS = ('January February March April May June July August September '
          'October November December').split()
ROW = re.compile(
    r'^\s*(?:(\d{4})\s+)?(' + '|'.join(MONTHS) + r')\s+'
    r'([\d.]+)\s+([\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-|-?[\d.]+)\s+(-|-?[\d.]+)',
    re.M,
)
BASE_PERIOD = date(2021, 1, 1)
DATA_FILE = Path(settings.BASE_DIR) / 'data' / 'official_ccpi_cbsl.json'


def parse_release_text(text):
    """Return {'YYYY-MM': record} from the 'Movement of the CCPI' table."""
    bases = re.findall(r'Movement of the CCPI \((\d{4})=100\)', text)
    if bases != ['2021']:
        raise CommandError(f'Expected one CCPI table on the 2021=100 base, found: {bases}')

    def number(value):
        return None if value == '-' else value

    records, year = {}, None
    for match in ROW.finditer(text):
        if match.group(1):
            year = int(match.group(1))
        if year is None:
            continue
        month = MONTHS.index(match.group(2)) + 1
        records[f'{year}-{month:02d}'] = {
            'ccpi': match.group(3), 'core': match.group(4),
            'mom': match.group(5), 'core_mom': match.group(6),
            'yoy': number(match.group(7)), 'core_yoy': number(match.group(8)),
        }
    if not records:
        raise CommandError('No CCPI rows found in that PDF.')
    return records


def _decimal(value):
    return None if value is None else Decimal(str(value))


class Command(BaseCommand):
    help = 'Report on, and optionally apply, official CBSL CCPI (2021=100) figures'

    def add_arguments(self, parser):
        parser.add_argument('--country', default='LKA')
        parser.add_argument('--pdf', help='Path to a CBSL CCPI press release PDF')
        parser.add_argument('--apply', action='store_true', help='Write changes (default: report only)')

    def handle(self, *args, **options):
        country = Country.objects.get(code=options['country'])
        records = {
            key: {**rec, 'note': f"Source: CBSL press release {rec['source']}."}
            for key, rec in json.loads(DATA_FILE.read_text()).items()
        }

        if options.get('pdf'):
            from pypdf import PdfReader
            text = '\n'.join(p.extract_text() or '' for p in PdfReader(options['pdf']).pages)
            name = Path(options['pdf']).name
            for key, rec in parse_release_text(text).items():
                # A blank Y-o-Y in the new table must not erase a known one.
                old = records.get(key, {})
                rec['yoy'] = rec['yoy'] if rec['yoy'] is not None else old.get('yoy')
                rec['core_yoy'] = rec['core_yoy'] if rec['core_yoy'] is not None else old.get('core_yoy')
                records[key] = {**rec, 'note': f'Source: CBSL press release {name}.'}

        added = corrected = unchanged = 0
        for key in sorted(records):
            rec = records[key]
            year, month = map(int, key.split('-'))
            period = date(year, month, calendar.monthrange(year, month)[1])
            for index_type, value, mom, yoy in (
                ('official_ccpi', rec['ccpi'], rec['mom'], rec['yoy']),
                ('official_core_ccpi', rec['core'], rec['core_mom'], rec['core_yoy']),
            ):
                wanted = {
                    'index_value': _decimal(value),
                    'mom_inflation': _decimal(mom),
                    'yoy_inflation': _decimal(yoy),
                }
                # Older rows exist on both the 1st and the last day of the month.
                rows = list(CPIIndex.objects.filter(
                    country=country, index_type=index_type, group__isnull=True,
                    period_date__year=year, period_date__month=month,
                ))
                if not rows:
                    added += 1
                    self.stdout.write(f'ADD     {key} {index_type}: index={value} yoy={yoy} mom={mom}')
                    if options['apply']:
                        CPIIndex.objects.create(
                            country=country, index_type=index_type, group=None,
                            period_date=period, base_period=BASE_PERIOD,
                            methodology_note=f"Official CBSL/DCS CCPI (2021=100). {rec['note']}",
                            **wanted,
                        )
                    continue
                for row in rows:
                    diffs = {f: (getattr(row, f), new) for f, new in wanted.items() if getattr(row, f) != new}
                    if not diffs:
                        unchanged += 1
                        continue
                    corrected += 1
                    shown = ', '.join(f'{f.split("_")[0]} {a} -> {b}' for f, (a, b) in diffs.items())
                    self.stdout.write(f'CORRECT {key} {index_type} [{row.period_date}]: {shown}')
                    if options['apply']:
                        for field, new in wanted.items():
                            setattr(row, field, new)
                        row.methodology_note = f"Official CBSL/DCS CCPI (2021=100). {rec['note']}"
                        row.save()

        verb = 'Applied' if options['apply'] else 'Report only (nothing written)'
        self.stdout.write(self.style.SUCCESS(
            f'{verb}: {added} to add, {corrected} to correct, {unchanged} already right.'
        ))

"""
Management command: flag_suspect_rates

Lists USD/LKR rows that look wrong, so the owner can decide what to do with them.
Nothing is deleted. Approved rows are only hidden from the site, and can be restored.

    python3 manage.py flag_suspect_rates                         # list only
    python3 manage.py flag_suspect_rates --hide 2026-05-22 2026-06-03
    python3 manage.py flag_suspect_rates --restore 2026-06-03
"""

from datetime import date
from statistics import median

from django.core.management.base import BaseCommand

from core.models import ExchangeRate

# Before this date the series is monthly, so neighbours say little about a value.
DAILY_FROM = date(2026, 5, 1)
THRESHOLD_PCT = 1.5
WINDOW = 4


class Command(BaseCommand):
    help = 'List suspect USD/LKR rows; hide or restore rows the owner has approved'

    def add_arguments(self, parser):
        parser.add_argument('--country', default='LKA')
        parser.add_argument('--hide', nargs='+', metavar='YYYY-MM-DD')
        parser.add_argument('--restore', nargs='+', metavar='YYYY-MM-DD')
        parser.add_argument('--note', default='Hidden after owner review')

    def handle(self, *args, **options):
        base = ExchangeRate.objects.filter(country__code=options['country'], base_currency='USD')

        if options.get('hide'):
            count = base.filter(rate_date__in=options['hide']).update(
                is_excluded=True, review_note=options['note'][:200])
            self.stdout.write(self.style.SUCCESS(f'Hidden {count} rows.'))
        if options.get('restore'):
            count = base.filter(rate_date__in=options['restore']).update(
                is_excluded=False, review_note='')
            self.stdout.write(self.style.SUCCESS(f'Restored {count} rows.'))
        if options.get('hide') or options.get('restore'):
            return

        rows = list(base.filter(rate_date__gte=DAILY_FROM).order_by('rate_date'))
        self.stdout.write('date        rate      typical   diff%   source / reason')
        found = 0
        for i, row in enumerate(rows):
            neighbours = rows[max(0, i - WINDOW):i] + rows[i + 1:i + 1 + WINDOW]
            typical = median(float(n.rate) for n in neighbours)
            diff = (float(row.rate) - typical) / typical * 100
            if abs(diff) >= THRESHOLD_PCT:
                found += 1
                state = ' [hidden]' if row.is_excluded else ''
                self.stdout.write(
                    f'{row.rate_date}  {float(row.rate):8.2f}  {typical:8.2f}  {diff:+5.1f}   {row.source}{state}'
                )
        self.stdout.write(self.style.SUCCESS(f'{found} suspect rows of {len(rows)} checked.'))

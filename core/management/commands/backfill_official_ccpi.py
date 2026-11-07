"""
Retired. This command loaded a hand-typed table that did not match CBSL's
published figures (for example August 2023: 177.0 and -1.9%, against CBSL's
190.1 and +4.0%). Use load_official_ccpi, which reads CBSL's own releases.
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Retired: use load_official_ccpi instead'

    def handle(self, *args, **options):
        raise CommandError('backfill_official_ccpi is retired. Use: manage.py load_official_ccpi')

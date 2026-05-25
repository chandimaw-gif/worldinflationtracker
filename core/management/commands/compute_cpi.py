import calendar
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from dateutil.relativedelta import relativedelta

from core.models import Country, CPIIndex, ProductGroup
from cpi_engine.calculations import compute_cpi, compute_inflation_rates


class Command(BaseCommand):
    help = "Compute and store CPI indices for a given country and date range"

    def add_arguments(self, parser):
        parser.add_argument('--country', type=str, default='LKA', help='ISO 3166-1 alpha-3 country code')
        parser.add_argument('--start', type=str, help='Start date YYYY-MM (default: 12 months ago)')
        parser.add_argument('--end', type=str, help='End date YYYY-MM (default: current month)')
        parser.add_argument('--force', action='store_true', help='Overwrite existing CPIIndex records')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be computed without saving')

    def handle(self, *args, **options):
        country_code = options['country']
        try:
            country = Country.objects.get(code=country_code, is_active=True)
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Country {country_code} not found or not active"))
            return

        today = date.today()
        if options['end']:
            end_year, end_month = map(int, options['end'].split('-'))
            end_date = date(end_year, end_month, 1)
        else:
            end_date = date(today.year, today.month, 1)

        if options['start']:
            start_year, start_month = map(int, options['start'].split('-'))
            start_date = date(start_year, start_month, 1)
        else:
            start_date = end_date - relativedelta(months=11)

        self.stdout.write(f"Computing CPI for {country.name} ({country.code})")
        self.stdout.write(f"Period: {start_date} to {end_date}")
        self.stdout.write(f"Base period: {country.base_period}")

        # Determine effective base period: use country's base_period if we have
        # at least some prices on or before it, otherwise fall back to earliest
        # observation date for this country.
        from core.models import PriceObservation
        earliest_obs = PriceObservation.objects.filter(
            country=country
        ).order_by('observation_date').first()

        if earliest_obs is None:
            self.stderr.write(self.style.ERROR("No price observations found. Run scrapers first."))
            return

        effective_base = country.base_period
        if effective_base and earliest_obs.observation_date > effective_base:
            self.stdout.write(self.style.WARNING(
                f"Base period {effective_base} has no observations. "
                f"Using earliest observation date {earliest_obs.observation_date} as base."
            ))
            effective_base = earliest_obs.observation_date
        elif effective_base is None:
            effective_base = earliest_obs.observation_date
            self.stdout.write(self.style.WARNING(f"No base period set. Using {effective_base}"))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        current = start_date
        while current <= end_date:
            # Use last day of month for period_date so we capture all prices in that month
            last_day = calendar.monthrange(current.year, current.month)[1]
            period_date = date(current.year, current.month, last_day)

            for index_type, label in CPIIndex.INDEX_TYPE_CHOICES:
                # Skip non_food for now (can be added later)
                if index_type == 'non_food':
                    continue

                existing = CPIIndex.objects.filter(
                    country=country,
                    period_date=period_date,
                    index_type=index_type,
                    group__isnull=True
                ).first()

                if existing and not options['force']:
                    skipped_count += 1
                    continue

                index_value = compute_cpi(
                    country, period_date, index_type=index_type, base_period=effective_base
                )

                if index_value is None:
                    self.stdout.write(
                        f"  {period_date} {label}: insufficient data"
                    )
                    continue

                yoy, mom, ma12 = compute_inflation_rates(
                    country, period_date, index_type=index_type
                )

                if options['dry_run']:
                    self.stdout.write(
                        f"  [DRY RUN] {period_date} {label}: {index_value:.2f} "
                        f"(YoY={yoy:.2f if yoy else 'N/A'}%, MoM={mom:.2f if mom else 'N/A'}%)"
                    )
                    continue

                if existing:
                    existing.index_value = index_value
                    existing.yoy_inflation = yoy
                    existing.mom_inflation = mom
                    existing.ma12_inflation = ma12
                    existing.base_period = effective_base
                    existing.save()
                    updated_count += 1
                else:
                    CPIIndex.objects.create(
                        country=country,
                        period_date=period_date,
                        index_type=index_type,
                        index_value=index_value,
                        yoy_inflation=yoy,
                        mom_inflation=mom,
                        ma12_inflation=ma12,
                        base_period=effective_base,
                        methodology_note=f"Computed from scraped/entered price observations. Base={effective_base}"
                    )
                    created_count += 1

                self.stdout.write(
                    f"  {period_date} {label}: {index_value:.2f} "
                    f"(YoY={f'{yoy:.2f}' if yoy else 'N/A'}%, MoM={f'{mom:.2f}' if mom else 'N/A'}%)"
                )

            current += relativedelta(months=1)

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No changes saved."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}"
            ))

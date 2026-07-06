import csv
import requests
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from core.models import BankExchangeRate

RATES_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSE_6nH-_hbGILUwWNJ3R89MWgSRAwSPU0eYlABobvV8VvR2qbkiUVxCXoImuGHx29J_dIpRH3InXnb/pub?gid=314532917&single=true&output=csv"


class Command(BaseCommand):
    help = 'Import bank exchange rates from Google Sheet (picks 3 banks with data)'

    def handle(self, *args, **options):
        self.stdout.write("Fetching bank rates from Google Sheet...")
        try:
            response = requests.get(RATES_SHEET_URL, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch sheet: {e}"))
            return

        content = response.content.decode('utf-8-sig')
        reader = csv.reader(content.strip().split('\n'))
        rows = list(reader)

        if not rows or len(rows) < 2:
            self.stdout.write(self.style.ERROR("No data in sheet"))
            return

        # Header row: Bank,,31-May-26,01-Jun-26,...
        header = rows[0]
        dates = []
        for col in header[2:]:
            col = col.strip()
            if col:
                try:
                    dt = datetime.strptime(col, '%d-%b-%y').date()
                    dates.append((col, dt))
                except ValueError:
                    pass

        if not dates:
            self.stdout.write(self.style.ERROR("No dates found in header"))
            return

        # Find the latest date with data
        latest_date_str = dates[-1][0]
        latest_date = dates[-1][1]
        try:
            latest_col_idx = header.index(latest_date_str)
        except ValueError:
            latest_col_idx = 2

        self.stdout.write(f"Using latest date: {latest_date} (column: {latest_date_str})")

        # Parse bank rows
        bank_data = {}
        current_bank = None

        for row in rows[1:]:
            if not row or len(row) < 3:
                continue

            bank_col = row[0].strip()
            rate_type = row[1].strip()

            if bank_col:
                current_bank = bank_col

            if not current_bank or not rate_type:
                continue

            # Parse rate type: "USD Buy", "USD Sell", etc.
            parts = rate_type.split()
            if len(parts) != 2:
                continue

            currency = parts[0]
            buy_sell = parts[1].lower()

            if buy_sell not in ('buy', 'sell'):
                continue

            if latest_col_idx < len(row):
                val_str = row[latest_col_idx].strip()
            else:
                continue

            if not val_str:
                continue

            try:
                val = Decimal(val_str)
            except InvalidOperation:
                continue

            if current_bank not in bank_data:
                bank_data[current_bank] = {}
            if currency not in bank_data[current_bank]:
                bank_data[current_bank][currency] = {}

            bank_data[current_bank][currency][buy_sell] = val

        # Find banks with complete USD buy+sell data for latest date
        complete_banks = []
        for bank, currencies in bank_data.items():
            if 'USD' in currencies and 'buy' in currencies['USD'] and 'sell' in currencies['USD']:
                complete_banks.append(bank)

        if not complete_banks:
            self.stdout.write(self.style.WARNING("No banks with complete USD data for today"))
            return

        # Pick up to 3 banks
        selected_banks = complete_banks[:3]
        self.stdout.write(f"Selected banks: {', '.join(selected_banks)}")

        created = 0
        updated = 0

        for bank_name in selected_banks:
            for currency, rates in bank_data[bank_name].items():
                if 'buy' not in rates or 'sell' not in rates:
                    continue

                _, was_created = BankExchangeRate.objects.update_or_create(
                    bank_name=bank_name,
                    currency=currency,
                    defaults={
                        'buy_rate': rates['buy'],
                        'sell_rate': rates['sell'],
                        'updated_at': datetime.combine(latest_date, datetime.min.time()),
                    }
                )

                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Bank rates imported for {latest_date}. Created: {created}, Updated: {updated}"
        ))

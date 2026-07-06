import csv
import requests
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from core.models import ExchangeRate

USD_LKR_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSE_6nH-_hbGILUwWNJ3R89MWgSRAwSPU0eYlABobvV8VvR2qbkiUVxCXoImuGHx29J_dIpRH3InXnb/pub?gid=31393083&single=true&output=csv"


class Command(BaseCommand):
    help = 'Import USD/LKR CBSL TT Selling rate from Google Sheet'

    def handle(self, *args, **options):
        self.stdout.write("Fetching USD/LKR rate from Google Sheet...")
        try:
            response = requests.get(USD_LKR_SHEET_URL, timeout=30)
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

        # Header: Bank (Selling Rate),01-Jun-26,02-Jun-26,...
        header = rows[0]
        # Data row: CBSL TT Selling Rate,335.7046,335.7046,...
        data_row = rows[1]

        if len(data_row) < 2:
            self.stdout.write(self.style.ERROR("No rate data found"))
            return

        # Find the latest date with a rate
        latest_date = None
        latest_rate = None

        for i in range(1, len(header)):
            date_str = header[i].strip()
            rate_str = data_row[i].strip() if i < len(data_row) else ''

            if not date_str or not rate_str:
                continue

            try:
                dt = datetime.strptime(date_str, '%d-%b-%y').date()
                rate = Decimal(rate_str)
                latest_date = dt
                latest_rate = rate
            except (ValueError, InvalidOperation):
                continue

        if not latest_date or not latest_rate:
            self.stdout.write(self.style.ERROR("Could not find valid rate"))
            return

        # Save to database
        rate_obj, was_created = ExchangeRate.objects.update_or_create(
            rate_date=latest_date,
            base_currency='USD',
            local_currency='LKR',
            defaults={
                'rate': latest_rate,
                'source': 'CBSL TT Selling Rate (Google Sheet)',
            }
        )

        action = 'Created' if was_created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f"{action} USD/LKR rate for {latest_date}: {latest_rate} LKR/USD"
        ))

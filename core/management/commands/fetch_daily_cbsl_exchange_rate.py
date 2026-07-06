import requests
from bs4 import BeautifulSoup
from datetime import datetime
from django.core.management.base import BaseCommand
from core.models import ExchangeRate


class Command(BaseCommand):
    help = 'Fetch daily USD/LKR TT Selling rate from CBSL official website'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Overwrite existing dates')
        parser.add_argument('--date', type=str, help='Specific date to fetch (YYYY-MM-DD)')

    def handle(self, *args, **options):
        force = options['force']
        target_date_str = options.get('date')
        
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = datetime.now().date()
        
        # Check if already exists
        existing = ExchangeRate.objects.filter(
            rate_date=target_date,
            base_currency='USD',
            local_currency='LKR'
        ).first()
        
        if existing and not force:
            self.stdout.write(self.style.WARNING(
                f'Rate for {target_date} already exists: {existing.rate} (source: {existing.source}). Use --force to overwrite.'
            ))
            return
        
        # Fetch from CBSL Buy/Sell TT rates page
        url = 'https://www.cbsl.gov.lk/cbsl_custom/exratestt/exrates_resultstt.php'
        payload = {
            'lookupPage': 'lookup_daily_exchange_rates.php',
            'rangeType': 'dates',
            'txtStart': target_date.strftime('%Y-%m-%d'),
            'txtEnd': target_date.strftime('%Y-%m-%d'),
            'chk_cur[]': 'USD~United States Dollar',
            'submit_button': 'Submit',
        }
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch from CBSL: {e}'))
            return
        
        # Parse the HTML table
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', class_='rates')
        
        if not table:
            self.stdout.write(self.style.ERROR('Could not find rates table in CBSL response'))
            return
        
        rows = table.find('tbody').find_all('tr')
        if not rows:
            self.stdout.write(self.style.ERROR('No data rows found in rates table'))
            return
        
        cells = rows[0].find_all('td')
        if len(cells) < 3:
            self.stdout.write(self.style.ERROR(f'Unexpected table structure: {len(cells)} cells'))
            return
        
        date_text = cells[0].get_text(strip=True)
        buy_rate = cells[1].get_text(strip=True)
        sell_rate = cells[2].get_text(strip=True)
        
        try:
            rate_value = float(sell_rate)
        except ValueError:
            self.stdout.write(self.style.ERROR(f'Could not parse sell rate: {sell_rate}'))
            return
        
        # Save to database - SELLING rate is what we display
        rate, created = ExchangeRate.objects.update_or_create(
            rate_date=target_date,
            base_currency='USD',
            local_currency='LKR',
            defaults={
                'rate': rate_value,
                'source': 'CBSL Daily TT Selling Rate (cbsl.gov.lk)',
            }
        )
        
        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} CBSL selling rate for {target_date}: {rate_value} LKR/USD (Buy: {buy_rate})'
        ))

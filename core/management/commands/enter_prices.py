"""
Management command to manually enter prices for basket items.

Usage:
    python manage.py enter_prices --item "Rice — Nadu" --price 185.00
    python manage.py enter_prices --date 2024-05-20 --json manual_prices.json
    python manage.py enter_prices --list-items
"""

import json
from decimal import Decimal
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import BasketItem, PriceObservation, PriceAuditLog


class Command(BaseCommand):
    help = 'Manually enter prices for basket items'

    def add_arguments(self, parser):
        parser.add_argument('--item', type=str, help='Item name (partial match)')
        parser.add_argument('--price', type=float, help='Price value')
        parser.add_argument('--date', type=str, help='Observation date (YYYY-MM-DD), defaults to today')
        parser.add_argument('--json', type=str, help='Path to JSON file with prices')
        parser.add_argument('--list-items', action='store_true', help='List all active basket items')
        parser.add_argument('--country', type=str, default='LKA', help='Country code (default: LKA)')

    def handle(self, *args, **options):
        if options['list_items']:
            self.list_items(options['country'])
            return

        if options['json']:
            self.load_from_json(options['json'], options['date'], options['country'])
            return

        if options['item'] and options['price'] is not None:
            self.enter_single_price(
                item_name=options['item'],
                price=Decimal(str(options['price'])),
                observation_date_str=options['date'],
                country_code=options['country'],
            )
            return

        self.stdout.write(self.style.ERROR('Please provide either --item + --price, --json, or --list-items'))

    def list_items(self, country_code):
        items = BasketItem.objects.filter(
            country__code=country_code,
            is_active=True,
        ).order_by('group__coicop_code', 'name')

        self.stdout.write(self.style.SUCCESS(f'\nActive basket items for {country_code}:\n'))
        current_group = None
        for item in items:
            if item.group != current_group:
                current_group = item.group
                self.stdout.write(self.style.NOTICE(f"\n{current_group.coicop_code} — {current_group.name}"))
            self.stdout.write(f"  {item.name} ({item.unit}) — weight: {item.weight}")

    def enter_single_price(self, item_name, price, observation_date_str, country_code):
        try:
            item = BasketItem.objects.get(
                country__code=country_code,
                name=item_name,
                is_active=True,
            )
        except BasketItem.DoesNotExist:
            # Try partial match
            item = BasketItem.objects.filter(
                country__code=country_code,
                name__icontains=item_name,
                is_active=True,
            ).first()

            if not item:
                self.stdout.write(self.style.ERROR(f'Item not found: {item_name}'))
                return

        obs_date = date.today()
        if observation_date_str:
            obs_date = date.fromisoformat(observation_date_str)

        country = item.country

        # Create or update PriceObservation
        obs, created = PriceObservation.objects.update_or_create(
            item=item,
            country=country,
            observation_date=obs_date,
            defaults={
                'price': price,
                'currency_code': country.currency_code,
                'source_url': '',
                'source_name': 'Manual Entry',
                'scrape_method': 'manual',
                'raw_data': {'entered_via': 'management_command'},
                'is_validated': False,
            }
        )

        # Create audit log
        PriceAuditLog.objects.create(
            item=item,
            country=country,
            observation_date=obs_date,
            price=price,
            source_url='',
            source_name='Manual Entry',
            scrape_method='manual',
            product_page_title='',
            product_page_snapshot={'entered_via': 'management_command'},
        )

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} PriceObservation: {item.name} @ {price} on {obs_date}'
        ))

    def load_from_json(self, json_path, observation_date_str, country_code):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        obs_date = date.today()
        if observation_date_str:
            obs_date = date.fromisoformat(observation_date_str)

        today_str = str(obs_date)
        prices = data.get(today_str, data)

        created_count = 0
        updated_count = 0
        failed_count = 0

        for item_name, price_value in prices.items():
            if price_value is None:
                continue

            item = BasketItem.objects.filter(
                country__code=country_code,
                name__icontains=item_name,
                is_active=True,
            ).first()

            if not item:
                self.stdout.write(self.style.WARNING(f'Item not found: {item_name}'))
                failed_count += 1
                continue

            try:
                price = Decimal(str(price_value))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Invalid price for {item_name}: {price_value}'))
                failed_count += 1
                continue

            obs, created = PriceObservation.objects.update_or_create(
                item=item,
                country=item.country,
                observation_date=obs_date,
                defaults={
                    'price': price,
                    'currency_code': item.country.currency_code,
                    'source_url': '',
                    'source_name': 'Manual Entry (JSON)',
                    'scrape_method': 'manual',
                    'raw_data': {'entered_via': 'json_file'},
                    'is_validated': False,
                }
            )

            PriceAuditLog.objects.create(
                item=item,
                country=item.country,
                observation_date=obs_date,
                price=price,
                source_url='',
                source_name='Manual Entry (JSON)',
                scrape_method='manual',
                product_page_snapshot={'entered_via': 'json_file'},
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nLoaded {created_count} new, {updated_count} updated, {failed_count} failed.'
        ))

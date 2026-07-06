"""
Seed example ScrapeSource entries for Keells, Spar and CEYPETCO.
These are starting configurations; administrators can edit them via Django admin.
"""

from django.db import migrations


def seed_scrape_sources(apps, schema_editor):
    BasketItem = apps.get_model('core', 'BasketItem')
    ScrapeSource = apps.get_model('core', 'ScrapeSource')
    Country = apps.get_model('core', 'Country')

    lka = Country.objects.filter(code='LKA').first()
    if not lka:
        return

    def get_item(name_fragment):
        return BasketItem.objects.filter(country=lka, name__icontains=name_fragment, is_active=True).first()

    sources = [
        # Spar 2U via Shopify JSON API
        {
            'item_name': 'Sugar — White',
            'source_name': 'Spar - White Sugar 1kg',
            'url': 'https://spar2u.lk/products/spar-savemor-white-sugar-1kg.json',
            'selector_type': 'shopify',
            'selector': '',
            'multiplier': '1',
        },
        {
            'item_name': 'Dhal (Mysoor',
            'source_name': 'Spar - Red Dhal 1kg',
            'url': 'https://spar2u.lk/products/spar-savemor-red-dhal-1kg.json',
            'selector_type': 'shopify',
            'selector': '',
            'multiplier': '1',
        },
        {
            'item_name': 'Coconut Oil',
            'source_name': 'Spar - Sunup Coconut Oil 1L',
            'url': 'https://spar2u.lk/products/sunup-coconut-oil-1l.json',
            'selector_type': 'shopify',
            'selector': '',
            'multiplier': '1',
        },
        {
            'item_name': 'Eggs — Fresh',
            'source_name': 'Spar - Local Eggs Large 10-pack',
            'url': 'https://spar2u.lk/products/spar-local-eggs-large-10-pack.json',
            'selector_type': 'shopify',
            'selector': '',
            'multiplier': '0.1',  # price per egg
        },
        {
            'item_name': 'Chicken — Whole',
            'source_name': 'Spar - Bairaha Chicken Pre-cut 1kg',
            'url': 'https://spar2u.lk/products/bairaha-broiler-chicken-pre-cut-skinless-12-pieces.json',
            'selector_type': 'shopify',
            'selector': '1000',
            'multiplier': '1',
        },
        {
            'item_name': 'Milk Powder — Anchor',
            'source_name': 'Spar - Lakspray Milk Powder 1kg',
            'url': 'https://spar2u.lk/products/lakspray-milk-powder-pouch-1kg.json',
            'selector_type': 'shopify',
            'selector': '',
            'multiplier': '0.4',  # 400g equivalent from 1kg
        },
        {
            'item_name': 'Tea — Loose',
            'source_name': 'Spar - Steuarts Rosa Kahata Tea 200g',
            'url': 'https://spar2u.lk/products/steuarts-rosa-kahata-tea-200g.json',
            'selector_type': 'shopify',
            'selector': '',
            'multiplier': '1',
        },
        # CEYPETCO fuel table
        {
            'item_name': 'Petrol — Octane 92',
            'source_name': 'CEYPETCO - Petrol 92',
            'url': 'https://ceypetco.gov.lk/historical-prices/',
            'selector_type': 'ceypetco_fuel',
            'selector': 'LP 92',
            'multiplier': '1',
        },
        {
            'item_name': 'Petrol — Octane 95',
            'source_name': 'CEYPETCO - Petrol 95',
            'url': 'https://ceypetco.gov.lk/historical-prices/',
            'selector_type': 'ceypetco_fuel',
            'selector': 'LP 95',
            'multiplier': '1',
        },
        {
            'item_name': 'Auto Diesel',
            'source_name': 'CEYPETCO - Auto Diesel',
            'url': 'https://ceypetco.gov.lk/historical-prices/',
            'selector_type': 'ceypetco_fuel',
            'selector': 'LAD',
            'multiplier': '1',
        },
        # Keells (React SPA - requires Playwright)
        {
            'item_name': 'Rice — Nadu',
            'source_name': 'Keells - Nadu Rice 1kg',
            'url': 'https://www.keellssuper.com/product/keells-nadu-rice-1kg',
            'selector_type': 'css',
            'selector': '.price, .product-price, [class*="price"], span',
            'requires_js': True,
            'multiplier': '1',
        },
        {
            'item_name': 'Sugar — White',
            'source_name': 'Keells - White Sugar 1kg',
            'url': 'https://www.keellssuper.com/product/keells-white-sugar-1kg',
            'selector_type': 'css',
            'selector': '.price, .product-price, [class*="price"], span',
            'requires_js': True,
            'multiplier': '1',
        },
        {
            'item_name': 'Coconut Oil',
            'source_name': 'Keells - Coconut Oil 1L',
            'url': 'https://www.keellssuper.com/product/keells-coconut-oil-1l',
            'selector_type': 'css',
            'selector': '.price, .product-price, [class*="price"], span',
            'requires_js': True,
            'multiplier': '1',
        },
    ]

    for cfg in sources:
        item = get_item(cfg['item_name'])
        if not item:
            continue

        ScrapeSource.objects.get_or_create(
            item=item,
            source_name=cfg['source_name'],
            defaults={
                'url': cfg['url'],
                'selector_type': cfg['selector_type'],
                'selector': cfg['selector'],
                'price_multiplier': cfg['multiplier'],
                'currency_code': 'LKR',
                'requires_js': cfg.get('requires_js', False),
                'is_active': True,
                'scrape_frequency': 'daily',
            }
        )


def reverse_seed(apps, schema_editor):
    ScrapeSource = apps.get_model('core', 'ScrapeSource')
    ScrapeSource.objects.filter(source_name__in=[
        'Spar - White Sugar 1kg',
        'Spar - Red Dhal 1kg',
        'Spar - Sunup Coconut Oil 1L',
        'Spar - Local Eggs Large 10-pack',
        'Spar - Bairaha Chicken Pre-cut 1kg',
        'Spar - Lakspray Milk Powder 1kg',
        'Spar - Steuarts Rosa Kahata Tea 200g',
        'CEYPETCO - Petrol 92',
        'CEYPETCO - Petrol 95',
        'CEYPETCO - Auto Diesel',
        'Keells - Nadu Rice 1kg',
        'Keells - White Sugar 1kg',
        'Keells - Coconut Oil 1L',
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_scrapesource'),
    ]

    operations = [
        migrations.RunPython(seed_scrape_sources, reverse_seed),
    ]

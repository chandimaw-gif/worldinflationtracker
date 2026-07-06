# Generated manually: add scheduling fields to ScrapeSource and create YouTubeSource model

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


def seed_default_youtube_sources(apps, schema_editor):
    Country = apps.get_model('core', 'Country')
    YouTubeSource = apps.get_model('core', 'YouTubeSource')

    lka = Country.objects.filter(code='LKA').first()
    if not lka:
        return

    defaults = [
        {
            'name': 'Sri Lanka Inflation & Economy',
            'source_type': 'search',
            'query': 'Sri Lanka inflation economy 2026',
            'max_results': 5,
            'refresh_frequency': 'daily',
        },
        {
            'name': 'CBSL Monetary Policy',
            'source_type': 'search',
            'query': 'Sri Lanka CBSL monetary policy 2026',
            'max_results': 5,
            'refresh_frequency': 'daily',
        },
        {
            'name': 'Sri Lanka Rupee & Exchange Rate',
            'source_type': 'search',
            'query': 'Sri Lanka rupee exchange rate 2026',
            'max_results': 5,
            'refresh_frequency': 'daily',
        },
    ]

    for cfg in defaults:
        YouTubeSource.objects.get_or_create(
            country=lka,
            name=cfg['name'],
            defaults=cfg
        )


def reverse_seed(apps, schema_editor):
    YouTubeSource = apps.get_model('core', 'YouTubeSource')
    YouTubeSource.objects.filter(name__in=[
        'Sri Lanka Inflation & Economy',
        'CBSL Monetary Policy',
        'Sri Lanka Rupee & Exchange Rate',
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_seed_scrape_sources'),
    ]

    operations = [
        migrations.AddField(
            model_name='scrapesource',
            name='scrape_day_of_month',
            field=models.IntegerField(
                blank=True,
                help_text='For monthly frequency: which day of the month (1-31). Leave blank for 1st.',
                null=True,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)],
            ),
        ),
        migrations.AddField(
            model_name='scrapesource',
            name='scrape_day_of_week',
            field=models.IntegerField(
                blank=True,
                choices=[
                    (0, 'Monday'),
                    (1, 'Tuesday'),
                    (2, 'Wednesday'),
                    (3, 'Thursday'),
                    (4, 'Friday'),
                    (5, 'Saturday'),
                    (6, 'Sunday'),
                ],
                help_text='For weekly frequency: which day of the week (0=Monday). Leave blank for any day.',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='scrapesource',
            name='selector_type',
            field=models.CharField(
                choices=[
                    ('css', 'CSS Selector'),
                    ('xpath', 'XPath'),
                    ('regex', 'Regex on full page'),
                    ('json', 'JSON Path'),
                    ('shopify', 'Shopify Product Handle'),
                    ('ceypetco_fuel', 'CEYPETCO Fuel Table'),
                ],
                default='css',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='YouTubeSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Human-readable label', max_length=200)),
                ('source_type', models.CharField(choices=[('search', 'Search Query'), ('channel', 'Channel ID')], default='search', max_length=20)),
                ('query', models.CharField(help_text='YouTube search query or channel ID (for channel uploads)', max_length=500)),
                ('max_results', models.PositiveIntegerField(default=5, help_text='Max videos to fetch from this source')),
                ('refresh_frequency', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='daily', max_length=20)),
                ('refresh_day_of_week', models.IntegerField(blank=True, choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')], help_text='For weekly frequency: which day of the week (0=Monday). Leave blank for any day.', null=True)),
                ('refresh_day_of_month', models.IntegerField(blank=True, help_text='For monthly frequency: which day of the month (1-31). Leave blank for 1st.', null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)])),
                ('is_active', models.BooleanField(default=True)),
                ('last_fetched_at', models.DateTimeField(blank=True, null=True)),
                ('last_status', models.CharField(blank=True, max_length=20)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='youtube_sources', to='core.country')),
            ],
            options={
                'verbose_name_plural': 'YouTube Sources',
                'ordering': ['name'],
            },
        ),
        migrations.RunPython(seed_default_youtube_sources, reverse_seed),
    ]

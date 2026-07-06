# Generated manually for ScrapeSource model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_add_youtube_video_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScrapeSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_name', models.CharField(max_length=200)),
                ('url', models.URLField(max_length=500)),
                ('selector_type', models.CharField(choices=[('css', 'CSS Selector'), ('xpath', 'XPath'), ('regex', 'Regex'), ('json', 'JSON Path'), ('shopify', 'Shopify Product Handle'), ('ceypetco_fuel', 'CEYPETCO Fuel Table')], default='css', max_length=20)),
                ('selector', models.CharField(blank=True, max_length=500)),
                ('price_regex', models.CharField(blank=True, max_length=200)),
                ('price_multiplier', models.DecimalField(decimal_places=4, default=1, max_digits=10)),
                ('currency_code', models.CharField(default='LKR', max_length=3)),
                ('requires_js', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('scrape_frequency', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='daily', max_length=20)),
                ('last_price', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('last_status', models.CharField(blank=True, max_length=20)),
                ('last_error', models.TextField(blank=True)),
                ('last_scraped_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name_plural': 'Scrape Sources',
                'ordering': ['source_name', 'item'],
            },
        ),
        migrations.AddField(
            model_name='scrapesource',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scrape_sources', to='core.basketitem'),
        ),
        migrations.AlterUniqueTogether(
            name='scrapesource',
            unique_together={('item', 'source_name')},
        ),
    ]

from django.contrib import admin
from .models import (
    Country, ProductGroup, BasketItem, PriceObservation,
    CPIIndex, ExchangeRate, NewsArticle, ScrapeLog, ScrapeSource,
    AdPlacement, PriceAuditLog
)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'currency_code', 'base_period', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name', 'code']


@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ['coicop_code', 'name', 'country', 'weight', 'is_core', 'is_active']
    list_filter = ['country', 'is_core', 'is_active']
    list_editable = ['weight', 'is_active']
    search_fields = ['name', 'coicop_code']


@admin.register(BasketItem)
class BasketItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'unit', 'weight', 'scrape_frequency', 'requires_manual_entry', 'is_active']
    list_filter = ['country', 'group', 'scrape_frequency', 'requires_manual_entry', 'is_active']
    list_editable = ['weight', 'is_active']
    search_fields = ['name', 'brand', 'specification']


@admin.register(PriceObservation)
class PriceObservationAdmin(admin.ModelAdmin):
    list_display = ['item', 'observation_date', 'price', 'currency_code', 'scrape_method', 'is_validated']
    list_filter = ['country', 'scrape_method', 'is_validated', 'observation_date']
    search_fields = ['item__name', 'source_name']
    date_hierarchy = 'observation_date'


@admin.register(CPIIndex)
class CPIIndexAdmin(admin.ModelAdmin):
    list_display = ['country', 'period_date', 'index_type', 'group', 'index_value', 'yoy_inflation', 'mom_inflation']
    list_filter = ['country', 'index_type', 'period_date']
    date_hierarchy = 'period_date'


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['country', 'rate_date', 'base_currency', 'local_currency', 'rate']
    list_filter = ['country', 'base_currency']
    date_hierarchy = 'rate_date'


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'source_name', 'category', 'published_at', 'is_featured']
    list_filter = ['category', 'is_featured', 'source_name']
    search_fields = ['title', 'summary']
    date_hierarchy = 'published_at'


@admin.register(ScrapeLog)
class ScrapeLogAdmin(admin.ModelAdmin):
    list_display = ['job_name', 'country', 'started_at', 'status', 'items_scraped', 'items_failed']
    list_filter = ['status', 'country', 'started_at']
    date_hierarchy = 'started_at'


@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    list_display = ['slot_name', 'ad_type', 'is_active', 'display_order', 'start_date', 'end_date']
    list_editable = ['ad_type', 'is_active', 'display_order']
    list_filter = ['ad_type', 'is_active']


@admin.register(PriceAuditLog)
class PriceAuditLogAdmin(admin.ModelAdmin):
    list_display = ['item', 'observation_date', 'price', 'source_name', 'scrape_method', 'created_at']
    list_filter = ['country', 'scrape_method', 'observation_date']
    date_hierarchy = 'observation_date'


@admin.register(ScrapeSource)
class ScrapeSourceAdmin(admin.ModelAdmin):
    list_display = [
        'item', 'source_name', 'url', 'selector_type', 'is_active',
        'requires_js', 'last_price', 'last_status', 'last_scraped_at'
    ]
    list_filter = ['is_active', 'requires_js', 'selector_type', 'country', 'scrape_frequency', 'last_status']
    search_fields = ['item__name', 'source_name', 'url', 'notes']
    list_editable = ['is_active']
    readonly_fields = ['last_price', 'last_price_date', 'last_status', 'last_error', 'last_scraped_at', 'created_at', 'updated_at']


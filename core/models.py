from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Country(models.Model):
    code = models.CharField(max_length=3, primary_key=True, help_text="ISO 3166-1 alpha-3")
    name = models.CharField(max_length=100)
    currency_code = models.CharField(max_length=3)
    currency_symbol = models.CharField(max_length=5, blank=True)
    base_period = models.DateField(help_text="e.g., 2022-01-01")
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Countries"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class ProductGroup(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='product_groups')
    coicop_code = models.CharField(max_length=10, blank=True, help_text="e.g., '01', '01.1'")
    name = models.CharField(max_length=200)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    weight = models.DecimalField(max_digits=8, decimal_places=4, validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_core = models.BooleanField(default=True, help_text="Included in core CPI?")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Product Groups"
        unique_together = ['country', 'coicop_code']
        ordering = ['country', 'coicop_code']

    def __str__(self):
        return f"{self.name} ({self.country.code})"


class BasketItem(models.Model):
    SCRAPE_FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
    ]

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='basket_items')
    group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=300)
    unit = models.CharField(max_length=100, help_text="e.g., '1 kg (bulk)', '1 litre'")
    brand = models.CharField(max_length=200, blank=True)
    specification = models.TextField(blank=True, help_text="Detailed description for like-for-like comparison")
    weight = models.DecimalField(max_digits=8, decimal_places=6, validators=[MinValueValidator(0)])
    scrape_source_primary = models.URLField(max_length=500, blank=True)
    scrape_source_backup = models.URLField(max_length=500, blank=True)
    scrape_frequency = models.CharField(max_length=20, choices=SCRAPE_FREQUENCY_CHOICES, default='daily')
    requires_manual_entry = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Basket Items"
        ordering = ['group', 'name']

    def __str__(self):
        return f"{self.name} ({self.unit})"


class PriceObservation(models.Model):
    METHOD_CHOICES = [
        ('automated', 'Automated'),
        ('manual', 'Manual'),
        ('api', 'API'),
    ]

    item = models.ForeignKey(BasketItem, on_delete=models.CASCADE, related_name='observations')
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='price_observations')
    observation_date = models.DateField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency_code = models.CharField(max_length=3)
    source_url = models.TextField(blank=True)
    source_name = models.CharField(max_length=200, blank=True)
    scrape_method = models.CharField(max_length=50, choices=METHOD_CHOICES, default='automated')
    raw_data = models.JSONField(blank=True, null=True, help_text="Store raw scraped data for audit")
    is_validated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Price Observations"
        indexes = [
            models.Index(fields=['country', 'observation_date']),
            models.Index(fields=['item', 'observation_date']),
        ]
        ordering = ['-observation_date', 'item']

    def __str__(self):
        return f"{self.item.name} @ {self.price} on {self.observation_date}"


class CPIIndex(models.Model):
    INDEX_TYPE_CHOICES = [
        ('headline', 'Headline CPI'),
        ('core', 'Core CPI'),
        ('food', 'Food CPI'),
        ('non_food', 'Non-Food CPI'),
        ('official_ccpi', 'Official CCPI (CBSL/DCS, 2021=100)'),
        ('official_core_ccpi', 'Official Core CCPI (CBSL/DCS, 2021=100)'),
    ]

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='cpi_indices')
    period_date = models.DateField(help_text="First of month")
    index_type = models.CharField(max_length=30, choices=INDEX_TYPE_CHOICES)
    group = models.ForeignKey(ProductGroup, on_delete=models.CASCADE, null=True, blank=True, related_name='cpi_indices')
    index_value = models.DecimalField(max_digits=10, decimal_places=4)
    yoy_inflation = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    mom_inflation = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    ma12_inflation = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    base_period = models.DateField()
    methodology_note = models.TextField(blank=True)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "CPI Indices"
        unique_together = ['country', 'period_date', 'index_type', 'group']
        ordering = ['-period_date', 'index_type']

    def __str__(self):
        return f"{self.index_type} {self.country.code} {self.period_date}: {self.index_value}"


class ExchangeRate(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='exchange_rates')
    rate_date = models.DateField()
    base_currency = models.CharField(max_length=3, default='USD')
    local_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=12, decimal_places=4, help_text="Local per 1 USD")
    source = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Exchange Rates"
        unique_together = ['country', 'rate_date', 'base_currency']
        ordering = ['-rate_date']

    def __str__(self):
        return f"{self.base_currency}/{self.local_currency} @ {self.rate} ({self.rate_date})"


class NewsArticle(models.Model):
    CATEGORY_CHOICES = [
        ('economy', 'Economy'),
        ('policy', 'Policy'),
        ('markets', 'Markets'),
        ('international', 'International'),
    ]

    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True, related_name='news_articles')
    title = models.TextField()
    summary = models.TextField(blank=True)
    source_name = models.CharField(max_length=200)
    source_url = models.TextField(unique=True)
    published_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "News Articles"
        ordering = ['-published_at']

    def __str__(self):
        return f"{self.title[:80]}... — {self.source_name}"


class ScrapeLog(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('success', 'Success'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
    ]

    job_name = models.CharField(max_length=200)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True, related_name='scrape_logs')
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    items_scraped = models.IntegerField(default=0)
    items_failed = models.IntegerField(default=0)
    error_log = models.TextField(blank=True)
    source_url = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Scrape Logs"
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.job_name} ({self.status}) @ {self.started_at}"




class ScrapeSource(models.Model):
    """
    Configurable scraping source for a basket item.
    Allows admins to add/edit scraping targets without code changes.
    """
    SELECTOR_TYPE_CHOICES = [
        ('css', 'CSS Selector'),
        ('xpath', 'XPath'),
        ('regex', 'Regex on full page'),
    ]

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='scrape_sources')
    item = models.ForeignKey(BasketItem, on_delete=models.CASCADE, related_name='scrape_sources')
    source_name = models.CharField(max_length=200, help_text="e.g., Keells, Spar, CEYPETCO")
    url = models.URLField(max_length=1000)
    selector_type = models.CharField(max_length=20, choices=SELECTOR_TYPE_CHOICES, default='css')
    selector = models.TextField(help_text="CSS selector, XPath, or regex pattern")
    price_regex = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional regex to extract numeric price from selected text (e.g., '([0-9,]+\\.\\d{2})')"
    )
    price_multiplier = models.DecimalField(
        max_digits=10, decimal_places=4, default=1,
        help_text="Multiply scraped price by this factor (e.g., 1000 for 'per kg' if site shows per gram)"
    )
    currency_code = models.CharField(max_length=3, default='LKR')
    requires_js = models.BooleanField(default=False, help_text="Use Playwright for JavaScript-rendered pages")
    is_active = models.BooleanField(default=True)
    scrape_frequency = models.CharField(
        max_length=20,
        choices=BasketItem.SCRAPE_FREQUENCY_CHOICES,
        default='daily'
    )
    notes = models.TextField(blank=True, help_text="Any notes about this source")

    # Tracking fields
    last_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    last_price_date = models.DateField(null=True, blank=True)
    last_status = models.CharField(max_length=20, blank=True)
    last_error = models.TextField(blank=True)
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Scrape Sources"
        ordering = ['item__name', 'source_name']

    def __str__(self):
        return f"{self.item.name} from {self.source_name}"


class AdPlacement(models.Model):
    AD_TYPE_CHOICES = [
        ('adsense', 'AdSense'),
        ('manual', 'Manual'),
        ('custom', 'Custom HTML'),
    ]

    slot_name = models.CharField(max_length=100, unique=True, help_text="e.g., 'header_banner', 'sidebar_1'")
    ad_type = models.CharField(max_length=20, choices=AD_TYPE_CHOICES)
    adsense_slot_id = models.CharField(max_length=100, blank=True)
    manual_image_url = models.TextField(blank=True)
    manual_link_url = models.TextField(blank=True)
    manual_alt_text = models.CharField(max_length=200, blank=True)
    manual_html = models.TextField(blank=True, help_text="Custom ad HTML/JS")
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Ad Placements"
        ordering = ['display_order', 'slot_name']

    def __str__(self):
        return f"{self.slot_name} ({self.ad_type})"


class PriceAuditLog(models.Model):
    METHOD_CHOICES = [
        ('automated', 'Automated'),
        ('manual', 'Manual'),
        ('api', 'API'),
    ]

    item = models.ForeignKey(BasketItem, on_delete=models.CASCADE, related_name='audit_logs')
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='price_audit_logs')
    observation_date = models.DateField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    source_url = models.TextField()
    source_name = models.CharField(max_length=200)
    scrape_method = models.CharField(max_length=50, choices=METHOD_CHOICES)
    product_page_title = models.TextField(blank=True)
    product_page_snapshot = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Price Audit Logs"
        ordering = ['-created_at']

    def __str__(self):
        return f"Audit: {self.item.name} @ {self.price} ({self.observation_date})"


class MarketRate(models.Model):
    """
    Stores CBSL and other official market rates:
    - Exchange rates (USD/LKR indicative)
    - Interest rates (AWPLR, TBill, SDFR, SLFR, OPR)
    """
    RATE_TYPE_CHOICES = [
        ('exchange_rate', 'Exchange Rate'),
        ('awplr', 'AWPLR — Average Weighted Prime Lending Rate'),
        ('awfdr', 'AWFDR — Average Weighted Fixed Deposit Rate'),
        ('tbill_91', 'Treasury Bill — 91 Day'),
        ('tbill_182', 'Treasury Bill — 182 Day'),
        ('tbill_364', 'Treasury Bill — 364 Day'),
        ('sdfr', 'Standing Deposit Facility Rate (SDFR)'),
        ('slfr', 'Standing Lending Facility Rate (SLFR)'),
        ('opr', 'Overnight Policy Rate (OPR)'),
    ]

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='market_rates')
    rate_date = models.DateField()
    rate_type = models.CharField(max_length=30, choices=RATE_TYPE_CHOICES)
    currency = models.CharField(max_length=3, blank=True, help_text="For exchange rates")
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    source = models.CharField(max_length=200, blank=True, default='CBSL')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Market Rates"
        unique_together = ['country', 'rate_date', 'rate_type', 'currency']
        ordering = ['-rate_date', 'rate_type']

    def __str__(self):
        return f"{self.rate_type} {self.rate_date}: {self.rate}"


class BankExchangeRate(models.Model):
    """
    Exchange rates published by individual commercial banks.
    """
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='bank_exchange_rates')
    bank_name = models.CharField(max_length=200)
    rate_date = models.DateField()
    currency = models.CharField(max_length=3)
    buying_rate = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    selling_rate = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    tt_buying_rate = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Telegraphic Transfer buying")
    tt_selling_rate = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Telegraphic Transfer selling")
    source_url = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Bank Exchange Rates"
        unique_together = ['country', 'bank_name', 'rate_date', 'currency']
        ordering = ['-rate_date', 'bank_name', 'currency']

    def __str__(self):
        return f"{self.bank_name} {self.currency} @ {self.rate_date}: Buy {self.buying_rate} / Sell {self.selling_rate}"


class YouTubeVideo(models.Model):
    """YouTube videos about Sri Lanka economy/inflation for homepage display."""
    country = models.ForeignKey(Country, on_delete=models.CASCADE,
                                related_name='youtube_videos')
    video_id = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=500)
    channel_name = models.CharField(max_length=200)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    view_count = models.BigIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "YouTube Videos"
        ordering = ['display_order', '-view_count']

    def __str__(self):
        return f"{self.title[:60]} ({self.channel_name})"

    @property
    def youtube_url(self):
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def embed_url(self):
        return f"https://www.youtube.com/embed/{self.video_id}"

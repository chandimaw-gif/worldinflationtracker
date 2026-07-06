import json
from datetime import date, timedelta
from decimal import Decimal

from django.views.generic import TemplateView, ListView
from django.shortcuts import get_object_or_404
from dateutil.relativedelta import relativedelta

from core.models import Country, PriceObservation, NewsArticle, ExchangeRate, CPIIndex, ProductGroup, BasketItem, YouTubeVideo
from cpi_engine.calculations import compute_cpi, compute_inflation_rates


class HomeView(TemplateView):
    template_name = 'frontend/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countries'] = Country.objects.filter(is_active=True)

        country_code = self.request.GET.get('country', 'LKA')
        try:
            country = Country.objects.get(code=country_code, is_active=True)
        except Country.DoesNotExist:
            country = Country.objects.filter(is_active=True).first()
        context['current_country'] = country
        context['current_month_year'] = date.today().strftime('%B %Y')

        if country:
            context.update(self._get_cpi_context(country))
            context.update(self._get_exchange_rate_context(country))
            context.update(self._get_news_context(country))
            context.update(self._get_chart_context(country))
            context['youtube_videos'] = YouTubeVideo.objects.filter(
                country=country
            ).order_by('display_order')[:6]

        return context

    def _get_cpi_context(self, country):
        """Fetch latest official CBSL CCPI data for the stat cards."""
        ctx = {}

        # Official headline CCPI (primary source — CBSL/DCS)
        official = CPIIndex.objects.filter(
            country=country,
            index_type='official_ccpi',
            group__isnull=True,
        ).order_by('-period_date').first()
        ctx['official_ccpi'] = official

        # Official core CCPI
        official_core = CPIIndex.objects.filter(
            country=country,
            index_type='official_core_ccpi',
            group__isnull=True,
        ).order_by('-period_date').first()
        ctx['official_core_ccpi'] = official_core

        # WIT's own calculated CPI (for comparison — shown separately)
        wit_headline = CPIIndex.objects.filter(
            country=country,
            index_type='headline',
            group__isnull=True,
        ).order_by('-period_date').first()
        ctx['wit_headline_cpi'] = wit_headline

        return ctx

    def _get_exchange_rate_context(self, country):
        """Fetch latest exchange rate."""
        ctx = {}
        latest_rate = ExchangeRate.objects.filter(
            country=country,
            base_currency='USD'
        ).order_by('-rate_date').first()
        ctx['latest_exchange_rate'] = latest_rate
        return ctx

    def _get_news_context(self, country):
        """Fetch latest 9 news articles — sheet articles first, then RSS."""
        ctx = {}

        # Featured articles from Google Sheet (curated, priority)
        featured = list(NewsArticle.objects.filter(
            country=country,
            is_featured=True,
        ).order_by('-published_at')[:9])

        # Fill remaining slots with RSS articles
        remaining = 9 - len(featured)
        if remaining > 0:
            featured_ids = [a.id for a in featured]
            rss_articles = list(NewsArticle.objects.filter(
                country=country,
                is_featured=False,
            ).exclude(
                id__in=featured_ids
            ).order_by('-published_at')[:remaining])
            articles = featured + rss_articles
        else:
            articles = featured

        # Fallback to global articles if still not enough
        if len(articles) < 9:
            existing_ids = [a.id for a in articles]
            global_articles = list(NewsArticle.objects.filter(
                country__isnull=True
            ).exclude(id__in=existing_ids).order_by('-published_at')[:9 - len(articles)])
            articles = articles + global_articles

        ctx['news_articles'] = articles
        return ctx

    def _get_chart_context(self, country):
        """Build chart data using official CBSL CCPI data (2022–present)."""
        ctx = {}

        # Fetch all official CCPI records ordered chronologically
        official_qs = CPIIndex.objects.filter(
            country=country,
            index_type='official_ccpi',
            group__isnull=True,
        ).order_by('period_date')

        core_qs = CPIIndex.objects.filter(
            country=country,
            index_type='official_core_ccpi',
            group__isnull=True,
        ).order_by('period_date')

        # Build lookup dicts: (year, month) → record
        official_by_month = {
            (r.period_date.year, r.period_date.month): r
            for r in official_qs
        }
        core_by_month = {
            (r.period_date.year, r.period_date.month): r
            for r in core_qs
        }
        wit_by_month = {
            (r.period_date.year, r.period_date.month): r
            for r in CPIIndex.objects.filter(
                country=country,
                index_type='headline',
                group__isnull=True,
            )
        }

        # Build unified month list spanning all available data
        # Include WIT-estimated months so recent months (before official CBSL release) appear
        all_months = sorted(set(official_by_month.keys()) | set(core_by_month.keys()) | set(wit_by_month.keys()))

        chart_data = {
            'labels': [],
            'official_ccpi': [],
            'official_core_ccpi': [],
            'official_yoy': [],
            'official_core_yoy': [],
            'wit_ccpi': [],
        }

        for yr, mo in all_months:
            import calendar
            label = date(yr, mo, 1).strftime('%b %Y')
            chart_data['labels'].append(label)

            rec = official_by_month.get((yr, mo))
            chart_data['official_ccpi'].append(float(rec.index_value) if rec else None)
            chart_data['official_yoy'].append(
                float(rec.yoy_inflation) if rec and rec.yoy_inflation is not None else None
            )

            core = core_by_month.get((yr, mo))
            chart_data['official_core_ccpi'].append(float(core.index_value) if core else None)
            chart_data['official_core_yoy'].append(
                float(core.yoy_inflation) if core and core.yoy_inflation is not None else None
            )

            wit = wit_by_month.get((yr, mo))
            chart_data['wit_ccpi'].append(float(wit.index_value) if wit else None)

        ctx['chart_data_json'] = json.dumps(chart_data)
        return ctx


class MethodologyView(TemplateView):
    template_name = 'frontend/methodology.html'


class AboutView(TemplateView):
    template_name = 'frontend/about.html'


class PriceLogView(ListView):
    template_name = 'frontend/price_log.html'
    model = PriceObservation
    paginate_by = 50
    context_object_name = 'prices'

    def get_queryset(self):
        queryset = PriceObservation.objects.select_related('item', 'country').all()
        country_code = self.request.GET.get('country')
        if country_code:
            queryset = queryset.filter(country__code=country_code)
        item_name = self.request.GET.get('item')
        if item_name:
            queryset = queryset.filter(item__name__icontains=item_name)
        return queryset.order_by('-observation_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countries'] = Country.objects.filter(is_active=True)
        context['selected_country'] = self.request.GET.get('country', '')
        context['selected_item'] = self.request.GET.get('item', '')
        return context


class ExchangeRateView(TemplateView):
    template_name = 'frontend/exchange_rates.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        country_code = self.kwargs.get('country', 'LKA')
        today = date.today()

        # All exchange rates for historical chart (up to ~3 years)
        rates_qs = ExchangeRate.objects.filter(
            country__code=country_code
        ).order_by('-rate_date')[:730]
        context['rates'] = rates_qs
        context['latest_rate'] = rates_qs.first()

        # Chart data (reversed for chronological order)
        chart_labels = []
        chart_data = []
        for r in reversed(list(rates_qs)):
            chart_labels.append(r.rate_date.strftime('%b %Y'))
            chart_data.append(float(r.rate))
        context['exchange_chart_json'] = json.dumps({
            'labels': chart_labels,
            'data': chart_data,
        })

        # 90-day stats (high / low / YoY) — computed from actual 90-day window
        ninety_days_ago = today - timedelta(days=90)
        rates_90d = ExchangeRate.objects.filter(
            country__code=country_code,
            rate_date__gte=ninety_days_ago
        ).order_by('-rate_date')
        if rates_90d:
            rates_90d_list = [float(r.rate) for r in rates_90d]
            context['high_rate'] = max(rates_90d_list)
            context['low_rate'] = min(rates_90d_list)
        else:
            # Fallback to all-time high/low if no 90-day data
            all_rates = ExchangeRate.objects.filter(country__code=country_code)
            if all_rates:
                all_list = [float(r.rate) for r in all_rates]
                context['high_rate'] = max(all_list)
                context['low_rate'] = min(all_list)
            else:
                context['high_rate'] = None
                context['low_rate'] = None

        # YoY change
        one_year_ago = today - timedelta(days=365)
        old_rate = ExchangeRate.objects.filter(
            country__code=country_code,
            rate_date__lte=one_year_ago
        ).order_by('-rate_date').first()
        if old_rate and context['latest_rate']:
            context['yoy_change'] = ((float(context['latest_rate'].rate) - float(old_rate.rate)) / float(old_rate.rate)) * 100
        else:
            context['yoy_change'] = None

        # Bank exchange rate comparison
        today = date.today()
        context['bank_rates'] = self._get_bank_comparison(country_code, today)

        # Market rates (interest rates)
        context['market_rates'] = self._get_market_rates(country_code, today)

        return context

    def _get_bank_comparison(self, country_code, today):
        from core.models import BankExchangeRate
        from django.db.models import Max, Q
        currencies = ['USD', 'GBP', 'EUR', 'AUD', 'CAD', 'SGD']

        # Preferred banks from Google Sheet (in priority order)
        bank_sources = [
            'Commercial Bank', 'NDB Bank', 'Seylan Bank',
            'Sampath Bank', 'HNB (Hatton National Bank)',
            'Bank of Ceylon (BOC)', 'DFCC Bank', 
        ]

        # Find the latest date that has at least 3 banks with both buy and sell rates
        latest_common_date = None
        dates_with_counts = (
            BankExchangeRate.objects
            .filter(country__code=country_code, currency='USD')
            .exclude(buying_rate__isnull=True, selling_rate__isnull=True)
            .values('rate_date')
            .annotate(bank_count=Max('id'))
            .order_by('-rate_date')
        )

        # Actually count valid banks per date
        from django.db.models import Count
        date_counts = (
            BankExchangeRate.objects
            .filter(
                country__code=country_code,
                currency='USD',
                buying_rate__isnull=False,
                selling_rate__isnull=False,
            )
            .values('rate_date')
            .annotate(count=Count('bank_name', distinct=True))
            .order_by('-rate_date')
        )

        for dc in date_counts:
            if dc['count'] >= 3:
                latest_common_date = dc['rate_date']
                break

        # If no date has 3 banks, use the overall latest date with any data
        if not latest_common_date:
            latest_rate = BankExchangeRate.objects.filter(
                country__code=country_code,
                currency='USD',
            ).order_by('-rate_date').first()
            if latest_rate:
                latest_common_date = latest_rate.rate_date

        # Determine which banks to show
        if latest_common_date:
            # Banks with both buy and sell on the latest common date
            banks_on_date = list(
                BankExchangeRate.objects.filter(
                    country__code=country_code,
                    currency='USD',
                    rate_date=latest_common_date,
                    buying_rate__isnull=False,
                    selling_rate__isnull=False,
                ).values_list('bank_name', flat=True).distinct()
            )
            banks_to_show = [b for b in bank_sources if b in banks_on_date][:3]

            # If fewer than 3 on that date, fall back to most recent data per bank
            if len(banks_to_show) < 3:
                recent_banks = list(
                    BankExchangeRate.objects.filter(
                        country__code=country_code,
                        currency='USD',
                        buying_rate__isnull=False,
                        selling_rate__isnull=False,
                    ).values_list('bank_name', flat=True).distinct()
                )
                for b in bank_sources:
                    if b in recent_banks and b not in banks_to_show:
                        banks_to_show.append(b)
                    if len(banks_to_show) >= 3:
                        break
        else:
            banks_to_show = []

        comparison = []
        for curr in currencies:
            row = {'currency': curr, 'banks': []}
            for bank in banks_to_show[:3]:
                rate = BankExchangeRate.objects.filter(
                    country__code=country_code,
                    bank_name=bank,
                    currency=curr,
                    buying_rate__isnull=False,
                    selling_rate__isnull=False,
                ).order_by('-rate_date').first()
                row['banks'].append({
                    'name': bank,
                    'buying': float(rate.buying_rate) if rate and rate.buying_rate else None,
                    'selling': float(rate.selling_rate) if rate and rate.selling_rate else None,
                    'date': str(rate.rate_date) if rate else None,
                })
            comparison.append(row)
        return comparison

    def _get_market_rates(self, country_code, today):
        from core.models import MarketRate
        rates = {}
        for rate_type, label in [
            ('awplr', 'AWPLR'),
            ('tbill_91', '91-Day T-Bill'),
            ('tbill_182', '182-Day T-Bill'),
            ('tbill_364', '364-Day T-Bill'),
            ('sdfr', 'SDFR'),
            ('slfr', 'SLFR'),
            ('opr', 'OPR'),
        ]:
            latest = MarketRate.objects.filter(
                country__code=country_code,
                rate_type=rate_type,
                rate_date__lte=today
            ).order_by('-rate_date').first()
            if latest:
                rates[label] = float(latest.rate)
        return rates


class DetailedAnalysisView(TemplateView):
    template_name = 'frontend/analysis.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countries'] = Country.objects.filter(is_active=True)

        country_code = self.request.GET.get('country', 'LKA')
        try:
            country = Country.objects.get(code=country_code, is_active=True)
        except Country.DoesNotExist:
            country = Country.objects.filter(is_active=True).first()
        context['current_country'] = country

        if country:
            context['product_groups'] = ProductGroup.objects.filter(
                country=country, is_active=True
            ).order_by('coicop_code')

            # Get items that have enough data for comparison
            context['basket_items'] = BasketItem.objects.filter(
                country=country, is_active=True
            ).select_related('group').order_by('name')

            # Chart data for selected items (default: show all)
            selected_items = self.request.GET.getlist('items')
            context['selected_item_ids'] = [int(i) for i in selected_items if i.isdigit()]
            if selected_items:
                items = BasketItem.objects.filter(id__in=selected_items, country=country).select_related('group').order_by('group__coicop_code', 'name')
            else:
                items = BasketItem.objects.filter(country=country, is_active=True).select_related('group').order_by('group__coicop_code', 'name')

            item_chart_data = self._build_item_chart_data(items, country)
            context['item_chart_data_json'] = json.dumps(item_chart_data)

        return context

    def _build_item_chart_data(self, items, country):
        """Build price history chart data for specific basket items."""
        end_date = date.today()
        start_date = end_date - relativedelta(months=11)

        # Build month labels
        months = []
        current = date(start_date.year, start_date.month, 1)
        while current <= end_date:
            import calendar
            last_day = calendar.monthrange(current.year, current.month)[1]
            months.append(date(current.year, current.month, last_day))
            current += relativedelta(months=1)

        datasets = []
        colors = ['#2563eb', '#dc2626', '#16a34a', '#ca8a04', '#9333ea',
                  '#0891b2', '#be123c', '#059669', '#d97706', '#7c3aed',
                  '#db2777', '#4f46e5', '#0d9488', '#b91c1c', '#65a30d']

        for i, item in enumerate(items):
            data = []
            for m in months:
                obs = PriceObservation.objects.filter(
                    item=item,
                    observation_date__lte=m
                ).order_by('-observation_date').first()
                data.append(float(obs.price) if obs else None)

            datasets.append({
                'label': item.name,
                'data': data,
                'borderColor': colors[i % len(colors)],
                'backgroundColor': colors[i % len(colors)] + '20',
                'fill': False,
                'tension': 0.3,
            })

        return {
            'labels': [m.strftime('%b %Y') for m in months],
            'datasets': datasets,
        }

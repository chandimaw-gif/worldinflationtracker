import csv
import datetime
import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import F, Max, Q
from django.http import HttpResponse
from django.views.generic import TemplateView, ListView
from django.shortcuts import get_object_or_404
from dateutil.relativedelta import relativedelta

from core.models import (
    Article, BankExchangeRate, BasketItem, Country, CPIIndex, ExchangeRate,
    MonthlyCommentary, NewsArticle, PriceObservation, ProductGroup, YouTubeVideo,
)
from cpi_engine.calculations import compute_cpi, compute_inflation_rates


logger = logging.getLogger('django')

# The 2021=100 CCPI series starts here. Earlier CBSL tables use 2013=100, so their
# index numbers cannot share a chart with this series.
OFFICIAL_SERIES_START = date(2022, 12, 1)

# Vertical markers shown on Sri Lankan CPI and exchange-rate charts
LKA_CHART_ANNOTATIONS = [
    {'date': 'Mar 2020', 'label': 'Start of Covid', 'color': '#dc2626', 'side': 'left'},
    {'date': 'Apr 2020', 'label': 'Start of economic crisis', 'color': '#ea580c', 'side': 'right'},
    {'date': 'Sep 2024', 'label': 'Presidential Election', 'color': '#7c3aed', 'side': 'left'},
    {'date': 'Nov 2024', 'label': 'General Election', 'color': '#7c3aed', 'side': 'right'},
]


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
            ).order_by('display_order')[:3]

        context['latest_article'] = Article.objects.filter(status=Article.PUBLISHED).order_by('-published_at').first()
        context['commentary'] = MonthlyCommentary.objects.filter(is_published=True).order_by('-month').first()

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

        return ctx

    def _get_exchange_rate_context(self, country):
        """Fetch latest exchange rate."""
        ctx = {}
        latest_rate = ExchangeRate.objects.filter(
            country=country,
            base_currency='USD',
            is_excluded=False,
        ).order_by('-rate_date').first()
        ctx['latest_exchange_rate'] = latest_rate
        return ctx

    def _get_news_context(self, country):
        """The five newest stories. The sheet repeats some headlines, so show each once."""
        ctx = {}
        candidates = NewsArticle.objects.filter(
            Q(country=country) | Q(country__isnull=True)
        ).order_by(F('published_at').desc(nulls_last=True))[:50]

        articles, seen = [], set()
        for article in candidates:
            key = article.title.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            articles.append(article)
            if len(articles) == 5:
                break

        ctx['news_articles'] = articles
        return ctx

    def _get_chart_context(self, country):
        """Build chart data from official CBSL CCPI figures only."""
        ctx = {}

        # Fetch all official CCPI records ordered chronologically
        official_qs = CPIIndex.objects.filter(
            country=country,
            index_type='official_ccpi',
            group__isnull=True,
            period_date__gte=OFFICIAL_SERIES_START,
        ).order_by('period_date')

        core_qs = CPIIndex.objects.filter(
            country=country,
            index_type='official_core_ccpi',
            group__isnull=True,
            period_date__gte=OFFICIAL_SERIES_START,
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
        # Build unified month list spanning all available data
        all_months = set(official_by_month.keys()) | set(core_by_month.keys())

        # Ensure annotation months appear on the axis even if official data starts later
        if country and country.code == 'LKA':
            for ann in LKA_CHART_ANNOTATIONS:
                ann_dt = datetime.datetime.strptime(ann['date'], '%b %Y').date()
                all_months.add((ann_dt.year, ann_dt.month))

        all_months = sorted(all_months)

        # Fill in every month between the first and last so the axis is continuous
        if all_months:
            min_year, min_month = all_months[0]
            max_year, max_month = all_months[-1]
            all_months = []
            cur = date(min_year, min_month, 1)
            end = date(max_year, max_month, 1)
            while cur <= end:
                all_months.append((cur.year, cur.month))
                cur += relativedelta(months=1)

        chart_data = {
            'labels': [],
            'official_ccpi': [],
            'official_core_ccpi': [],
            'official_yoy': [],
            'official_core_yoy': [],
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


        # Vertical markers for Sri Lankan charts
        if country and country.code == 'LKA':
            chart_data['annotations'] = list(LKA_CHART_ANNOTATIONS)

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

    def _filtered(self):
        queryset = PriceObservation.objects.select_related('item__group', 'country').all()
        country_code = self.request.GET.get('country')
        if country_code:
            queryset = queryset.filter(country__code=country_code)
        item_name = self.request.GET.get('item')
        if item_name:
            queryset = queryset.filter(item__name__icontains=item_name)
        return queryset

    @staticmethod
    def _change_ids():
        """Each item's first recorded price, plus every row where its price changed."""
        last_price = {}
        ids = []
        rows = PriceObservation.objects.order_by('observation_date', 'id').values_list('id', 'item_id', 'price')
        for row_id, item_id, price in rows:
            if last_price.get(item_id) != price:
                ids.append(row_id)
            last_price[item_id] = price
        return ids

    def get_queryset(self):
        queryset = self._filtered()
        if self.request.GET.get('view') != 'all':
            queryset = queryset.filter(id__in=self._change_ids())
        return queryset.order_by('-observation_date', 'item__name')

    def get(self, request, *args, **kwargs):
        if request.GET.get('export') == 'csv':
            return self._export_csv()
        return super().get(request, *args, **kwargs)

    def _export_csv(self):
        """The export always contains the full log, including unchanged prices."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="price-log.csv"'
        writer = csv.writer(response)
        writer.writerow(['date', 'item', 'unit', 'category', 'price', 'currency', 'source', 'source_url', 'method'])
        for p in self._filtered().order_by('-observation_date', 'item__name'):
            writer.writerow([
                p.observation_date, p.item.name, p.item.unit, p.item.group.name, p.price,
                p.currency_code, p.source_name, p.source_url, p.scrape_method,
            ])
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countries'] = Country.objects.filter(is_active=True)
        context['selected_country'] = self.request.GET.get('country', '')
        context['selected_item'] = self.request.GET.get('item', '')
        context['selected_view'] = 'all' if self.request.GET.get('view') == 'all' else 'changes'
        context['last_updated'] = PriceObservation.objects.aggregate(d=Max('observation_date'))['d']
        filters = {k: self.request.GET[k] for k in ('country', 'item') if self.request.GET.get(k)}
        context['filter_query'] = urlencode(filters)
        if context['selected_view'] == 'all':
            filters['view'] = 'all'
        context['page_query'] = urlencode(filters)
        return context


class ExchangeRateView(TemplateView):
    template_name = 'frontend/exchange_rates.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        country_code = self.kwargs.get('country', 'LKA')
        today = date.today()

        rates = ExchangeRate.objects.filter(country__code=country_code, is_excluded=False)

        # Recent rates for the table: last 30 unless the visitor asks for everything
        context['show_all_rates'] = self.request.GET.get('rows') == 'all'
        context['rates'] = rates.order_by('-rate_date')[:(730 if context['show_all_rates'] else 30)]
        context['total_rates'] = rates.count()
        latest = rates.order_by('-rate_date').first()
        context['latest_rate'] = latest

        # All exchange rates for historical chart (actual records only)
        origin = date(2020, 1, 1)
        chart_data = [
            {'x': (r.rate_date - origin).days, 'y': float(r.rate)}
            for r in rates.order_by('rate_date')
        ]

        x_max = (today - origin).days
        if chart_data:
            x_max = max(x_max, max(p['x'] for p in chart_data))

        exchange_chart_data = {
            'data': chart_data,
            'x_min': (date(2020, 3, 1) - origin).days,
            'x_max': x_max,
        }
        if country_code == 'LKA':
            exchange_chart_data['annotations'] = [
                {**ann, 'value': (datetime.datetime.strptime(ann['date'], '%b %Y').date() - origin).days}
                for ann in LKA_CHART_ANNOTATIONS
            ]
        context['exchange_chart_json'] = json.dumps(exchange_chart_data)

        # 90-day high and low
        values_90d = [float(v) for v in rates.filter(rate_date__gte=today - timedelta(days=90)).values_list('rate', flat=True)]
        context['high_rate'] = max(values_90d) if values_90d else None
        context['low_rate'] = min(values_90d) if values_90d else None

        # 12-month change: only ever compare a rate with the same source's rate a year
        # earlier. The sources measure different things (mid-market vs TT selling).
        context['yoy_change'] = None
        context['yoy_available_from'] = None
        if latest:
            same_source = rates.filter(source=latest.source)
            target = latest.rate_date - timedelta(days=365)
            old_rate = same_source.filter(
                rate_date__lte=target, rate_date__gte=target - timedelta(days=31)
            ).order_by('-rate_date').first()
            if old_rate:
                context['yoy_change'] = (float(latest.rate) - float(old_rate.rate)) / float(old_rate.rate) * 100
                context['yoy_compared_to'] = old_rate
            else:
                first = same_source.order_by('rate_date').first()
                context['yoy_available_from'] = first.rate_date + relativedelta(years=1)

        # Bank exchange rate comparison
        today = date.today()
        context['bank_rates'] = self._get_bank_comparison(country_code, today)

        # Market rates (interest rates)
        context['market_rates'] = self._get_market_rates(country_code, today)

        return context

    def _get_bank_comparison(self, country_code, today):
        currencies = ['USD', 'GBP', 'EUR', 'AUD', 'CAD', 'SGD']
        preferred = [
            'NDB Bank', 'Seylan Bank', "People's Bank", 'Bank of Ceylon (BOC)',
            'Commercial Bank', 'Sampath Bank', 'HNB (Hatton National Bank)', 'DFCC Bank',
        ]
        all_rows = BankExchangeRate.objects.filter(country__code=country_code)

        # Only compare banks whose USD quote is current and has both sides.
        usd = all_rows.filter(currency='USD', buying_rate__isnull=False, selling_rate__isnull=False)
        newest = usd.aggregate(d=Max('rate_date'))['d']
        if not newest:
            return []
        cutoff = newest - timedelta(days=7)
        bank_dates = {}
        for bank in preferred:
            row = usd.filter(bank_name=bank, rate_date__gte=cutoff).order_by('-rate_date').first()
            if row and self._valid_pair(row):
                bank_dates[bank] = row.rate_date
            if len(bank_dates) == 4:
                break

        comparison = []
        for curr in currencies:
            row = {'currency': curr, 'banks': [], 'has_data': False}
            for bank, as_of in bank_dates.items():
                rate = all_rows.filter(bank_name=bank, currency=curr, rate_date=as_of).first()
                ok = rate is not None and self._valid_pair(rate)
                buying = float(rate.buying_rate) if ok and rate.buying_rate else None
                selling = float(rate.selling_rate) if ok and rate.selling_rate else None
                row['has_data'] = row['has_data'] or buying is not None or selling is not None
                row['banks'].append({'name': bank, 'buying': buying, 'selling': selling, 'date': as_of})
            comparison.append(row)
        return comparison

    @staticmethod
    def _valid_pair(rate):
        """A bank's selling rate can never be below its buying rate."""
        if rate.buying_rate and rate.selling_rate and rate.selling_rate < rate.buying_rate:
            logger.warning(
                'Hid invalid bank rate: %s %s %s buy %s sell %s',
                rate.bank_name, rate.currency, rate.rate_date, rate.buying_rate, rate.selling_rate,
            )
            return False
        return True

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
            ('us_treasury_10y', 'US 10Y Treasury Yield'),
        ]:
            latest = MarketRate.objects.filter(
                country__code=country_code,
                rate_type=rate_type,
                rate_date__lte=today
            ).order_by('-rate_date').first()
            if latest:
                rates[label] = {'value': float(latest.rate), 'date': latest.rate_date}
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

            context['last_updated'] = PriceObservation.objects.filter(country=country).aggregate(d=Max('observation_date'))['d']
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

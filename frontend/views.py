import json
from datetime import date, timedelta
from decimal import Decimal

from django.views.generic import TemplateView, ListView
from django.shortcuts import get_object_or_404
from dateutil.relativedelta import relativedelta

from core.models import Country, PriceObservation, NewsArticle, ExchangeRate, CPIIndex, ProductGroup, BasketItem
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

        return context

    def _get_cpi_context(self, country):
        """Fetch latest CPI indices with YoY changes."""
        ctx = {}
        today = date.today()
        period_end = date(today.year, today.month, 1)

        for idx_type in ['headline', 'core', 'food']:
            # Try stored CPIIndex first
            latest = CPIIndex.objects.filter(
                country=country,
                index_type=idx_type,
                group__isnull=True
            ).order_by('-period_date').first()

            if latest:
                ctx[f'{idx_type}_cpi'] = latest
            else:
                # Fallback: compute on-the-fly for current month
                index_value = compute_cpi(country, period_end, index_type=idx_type)
                if index_value is not None:
                    yoy, mom, ma12 = compute_inflation_rates(country, period_end, index_type=idx_type)
                    ctx[f'{idx_type}_cpi'] = {
                        'index_value': index_value,
                        'yoy_inflation': yoy,
                        'mom_inflation': mom,
                        'period_date': period_end,
                        '_computed_on_the_fly': True,
                    }
                else:
                    ctx[f'{idx_type}_cpi'] = None

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
        """Fetch latest news articles."""
        ctx = {}
        articles = NewsArticle.objects.filter(
            country=country
        ).order_by('-published_at')[:6]
        # Also include global news (no country assigned)
        if articles.count() < 6:
            global_articles = NewsArticle.objects.filter(
                country__isnull=True
            ).order_by('-published_at')[:6 - articles.count()]
            articles = list(articles) + list(global_articles)
        ctx['news_articles'] = articles
        return ctx

    def _get_chart_context(self, country):
        """Build chart data for the last 24 months of CPI."""
        ctx = {}
        end_date = date.today()
        start_date = end_date - relativedelta(months=23)

        # Build a list of month-end dates
        months = []
        current = date(start_date.year, start_date.month, 1)
        while current <= end_date:
            import calendar
            last_day = calendar.monthrange(current.year, current.month)[1]
            months.append(date(current.year, current.month, last_day))
            current += relativedelta(months=1)

        chart_data = {
            'labels': [],
            'headline': [],
            'core': [],
            'food': [],
        }

        for m in months:
            label = m.strftime('%b %Y')
            chart_data['labels'].append(label)

            for idx_type in ['headline', 'core', 'food']:
                cpi = CPIIndex.objects.filter(
                    country=country,
                    index_type=idx_type,
                    group__isnull=True,
                    period_date__year=m.year,
                    period_date__month=m.month
                ).order_by('-period_date').first()

                if cpi:
                    chart_data[idx_type].append(float(cpi.index_value))
                else:
                    # Try to compute on-the-fly
                    val = compute_cpi(country, m, index_type=idx_type)
                    chart_data[idx_type].append(float(val) if val else None)

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
        rates_qs = ExchangeRate.objects.filter(
            country__code=country_code
        ).order_by('-rate_date')[:90]
        context['rates'] = rates_qs
        context['latest_rate'] = rates_qs.first()

        # Chart data
        chart_labels = []
        chart_data = []
        for r in reversed(list(rates_qs)):
            chart_labels.append(r.rate_date.strftime('%b %d'))
            chart_data.append(float(r.rate))
        context['exchange_chart_json'] = json.dumps({
            'labels': chart_labels,
            'data': chart_data,
        })

        # Stats
        if rates_qs:
            rates_list = [float(r.rate) for r in rates_qs]
            context['high_rate'] = max(rates_list)
            context['low_rate'] = min(rates_list)
            # YoY: compare latest with rate from ~1 year ago
            from datetime import timedelta
            one_year_ago = date.today() - timedelta(days=365)
            old_rate = ExchangeRate.objects.filter(
                country__code=country_code,
                rate_date__lte=one_year_ago
            ).order_by('-rate_date').first()
            if old_rate and context['latest_rate']:
                context['yoy_change'] = ((float(context['latest_rate'].rate) - float(old_rate.rate)) / float(old_rate.rate)) * 100
            else:
                context['yoy_change'] = None
        return context


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

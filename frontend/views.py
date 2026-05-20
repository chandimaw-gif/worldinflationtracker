from django.views.generic import TemplateView, ListView
from django.shortcuts import get_object_or_404
from core.models import Country, PriceObservation, NewsArticle, ExchangeRate, CPIIndex


class HomeView(TemplateView):
    template_name = 'frontend/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countries'] = Country.objects.filter(is_active=True)
        # Default to Sri Lanka if available
        try:
            context['current_country'] = Country.objects.get(code='LKA')
        except Country.DoesNotExist:
            context['current_country'] = None
        return context


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
        return queryset.order_by('-observation_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countries'] = Country.objects.filter(is_active=True)
        return context


class ExchangeRateView(TemplateView):
    template_name = 'frontend/exchange_rates.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        country_code = self.kwargs.get('country', 'LKA')
        context['rates'] = ExchangeRate.objects.filter(country__code=country_code).order_by('-rate_date')[:30]
        return context


class DetailedAnalysisView(TemplateView):
    template_name = 'frontend/analysis.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['countries'] = Country.objects.filter(is_active=True)
        return context

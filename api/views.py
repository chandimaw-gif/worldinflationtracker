from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.models import (
    Country, ProductGroup, BasketItem, PriceObservation,
    CPIIndex, ExchangeRate, NewsArticle, AdPlacement
)
from .serializers import (
    CountrySerializer, ProductGroupSerializer, BasketItemSerializer,
    PriceObservationSerializer, CPIIndexSerializer, ExchangeRateSerializer,
    NewsArticleSerializer, AdPlacementSerializer
)


class CountryListView(generics.ListAPIView):
    queryset = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer


class CountryDetailView(generics.RetrieveAPIView):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    lookup_field = 'code'


class ProductGroupListView(generics.ListAPIView):
    serializer_class = ProductGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_core', 'is_active']
    ordering_fields = ['weight', 'name']

    def get_queryset(self):
        country_code = self.kwargs['code']
        return ProductGroup.objects.filter(country__code=country_code, is_active=True)


class BasketItemListView(generics.ListAPIView):
    serializer_class = BasketItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['group', 'scrape_frequency', 'requires_manual_entry', 'is_active']
    search_fields = ['name', 'brand', 'specification']
    ordering_fields = ['name', 'weight']

    def get_queryset(self):
        country_code = self.kwargs['code']
        return BasketItem.objects.filter(country__code=country_code, is_active=True)


class PriceObservationListView(generics.ListAPIView):
    serializer_class = PriceObservationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['item', 'scrape_method', 'is_validated']
    ordering_fields = ['observation_date', 'price']

    def get_queryset(self):
        country_code = self.kwargs['code']
        return PriceObservation.objects.filter(country__code=country_code)


class CPIIndexListView(generics.ListAPIView):
    serializer_class = CPIIndexSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['index_type', 'group']
    ordering_fields = ['period_date', 'index_value']

    def get_queryset(self):
        country_code = self.kwargs['code']
        return CPIIndex.objects.filter(country__code=country_code)


class ExchangeRateListView(generics.ListAPIView):
    serializer_class = ExchangeRateSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['base_currency']
    ordering_fields = ['rate_date']

    def get_queryset(self):
        country_code = self.kwargs['code']
        return ExchangeRate.objects.filter(country__code=country_code)


class NewsArticleListView(generics.ListAPIView):
    serializer_class = NewsArticleSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['category', 'is_featured', 'source_name']
    ordering_fields = ['published_at', 'fetched_at']

    def get_queryset(self):
        country_code = self.kwargs.get('code')
        queryset = NewsArticle.objects.all()
        if country_code:
            queryset = queryset.filter(country__code=country_code)
        return queryset


class AdPlacementDetailView(generics.RetrieveAPIView):
    queryset = AdPlacement.objects.filter(is_active=True)
    serializer_class = AdPlacementSerializer
    lookup_field = 'slot_name'

from rest_framework import serializers
from core.models import (
    Country, ProductGroup, BasketItem, PriceObservation,
    CPIIndex, ExchangeRate, NewsArticle, AdPlacement
)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = '__all__'


class ProductGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductGroup
        fields = '__all__'


class BasketItemSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    coicop_code = serializers.CharField(source='group.coicop_code', read_only=True)

    class Meta:
        model = BasketItem
        fields = '__all__'


class PriceObservationSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_unit = serializers.CharField(source='item.unit', read_only=True)

    class Meta:
        model = PriceObservation
        fields = '__all__'


class CPIIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = CPIIndex
        fields = '__all__'


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = '__all__'


class NewsArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsArticle
        fields = '__all__'


class AdPlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdPlacement
        fields = '__all__'

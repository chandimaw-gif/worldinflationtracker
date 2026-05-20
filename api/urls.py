from django.urls import path
from . import views

urlpatterns = [
    path('countries/', views.CountryListView.as_view(), name='country-list'),
    path('countries/<str:code>/', views.CountryDetailView.as_view(), name='country-detail'),
    path('countries/<str:code>/groups/', views.ProductGroupListView.as_view(), name='group-list'),
    path('countries/<str:code>/items/', views.BasketItemListView.as_view(), name='item-list'),
    path('countries/<str:code>/prices/', views.PriceObservationListView.as_view(), name='price-list'),
    path('countries/<str:code>/cpi/', views.CPIIndexListView.as_view(), name='cpi-list'),
    path('countries/<str:code>/exchange-rates/', views.ExchangeRateListView.as_view(), name='exchange-rate-list'),
    path('countries/<str:code>/news/', views.NewsArticleListView.as_view(), name='news-list'),
    path('ads/<str:slot_name>/', views.AdPlacementDetailView.as_view(), name='ad-detail'),
]

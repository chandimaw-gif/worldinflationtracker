from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('methodology/', views.MethodologyView.as_view(), name='methodology'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('price-log/', views.PriceLogView.as_view(), name='price-log'),
    path('exchange-rates/', views.ExchangeRateView.as_view(), name='exchange-rates'),
    path('analysis/', views.DetailedAnalysisView.as_view(), name='analysis'),
]

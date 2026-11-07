from django.urls import path
from django.views.generic import RedirectView

from . import pages, views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('methodology/', views.MethodologyView.as_view(), name='methodology'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('price-log/', views.PriceLogView.as_view(), name='price-log'),
    path('exchange-rates/', views.ExchangeRateView.as_view(), name='exchange-rates'),
    path('analysis/', views.DetailedAnalysisView.as_view(), name='analysis'),
    path('privacy-policy/', pages.PrivacyPolicyView.as_view(), name='privacy-policy'),
    path('privacy/', RedirectView.as_view(pattern_name='privacy-policy', permanent=True)),
    path('terms/', pages.TermsView.as_view(), name='terms'),
    path('contact/', pages.ContactView.as_view(), name='contact'),
    path('insights/', pages.InsightsListView.as_view(), name='insights'),
    path('insights/<slug:slug>/', pages.ArticleDetailView.as_view(), name='article-detail'),
    path('robots.txt', pages.robots_txt, name='robots-txt'),
    path('sitemap.xml', pages.sitemap_xml, name='sitemap-xml'),
]

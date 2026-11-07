from django.conf import settings
from core.models import Article, Country, AdPlacement


def site_context(request):
    context = {
        'active_countries': Country.objects.filter(is_active=True),
    }
    context['site_url'] = settings.SITE_URL
    context['contact_email'] = settings.SITE_CONTACT_EMAIL
    context['site_owner_name'] = settings.SITE_OWNER_NAME
    context['site_owner_bio'] = settings.SITE_OWNER_BIO
    # An empty Insights section would look thin, so link to it once something is published.
    context['has_insights'] = Article.objects.filter(status=Article.PUBLISHED).exists()

    # Load active ads for template rendering
    ads = {}
    for ad in AdPlacement.objects.filter(is_active=True):
        ads[ad.slot_name] = ad
    context['ads'] = ads

    # Google AdSense config
    context['adsense'] = {
        'enabled': getattr(settings, 'GOOGLE_ADSENSE_ENABLED', False),
        'publisher_id': getattr(settings, 'GOOGLE_ADSENSE_PUBLISHER_ID', 'pub-XXXXXXXXXXXXXXXX'),
        'slots': getattr(settings, 'GOOGLE_ADSENSE_SLOTS', {}),
    }
    return context

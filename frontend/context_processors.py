from django.conf import settings
from core.models import Country, AdPlacement


def site_context(request):
    context = {
        'active_countries': Country.objects.filter(is_active=True),
    }
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

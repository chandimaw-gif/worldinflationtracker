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
    return context

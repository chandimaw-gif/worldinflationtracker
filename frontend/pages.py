"""Trust pages, articles and the files search engines read."""
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import escape
from django.views.generic import DetailView, FormView, ListView, TemplateView

from core.models import Article, ContactMessage
from .forms import ContactForm

logger = logging.getLogger('django')

MESSAGES_PER_HOUR = 5


class PrivacyPolicyView(TemplateView):
    template_name = 'frontend/privacy_policy.html'


class TermsView(TemplateView):
    template_name = 'frontend/terms.html'


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')


def _over_limit(request):
    """Limit messages per visitor. If the cache is down, allow the message."""
    ip = _client_ip(request)
    # Behind the proxy, a loopback address means the visitor's IP was not passed on.
    # Limiting that would count every visitor as one person.
    if ip in ('', '127.0.0.1', '::1'):
        return False
    key = f'contact-limit:{ip}'
    try:
        cache.add(key, 0, 3600)
        return cache.incr(key) > MESSAGES_PER_HOUR
    except Exception:
        logger.warning('Contact form rate limit unavailable', exc_info=True)
        return False


class ContactView(FormView):
    template_name = 'frontend/contact.html'
    form_class = ContactForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sent'] = self.request.GET.get('sent') == '1'
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        if not data['website']:  # A filled-in hidden field means spam: pretend it worked.
            if _over_limit(self.request):
                form.add_error(None, 'Too many messages from your connection. Please try again later.')
                return self.form_invalid(form)
            ContactMessage.objects.create(
                name=data['name'], email=data['email'],
                subject=data['subject'], message=data['message'],
            )
        return redirect(reverse('contact') + '?sent=1')


class InsightsListView(ListView):
    template_name = 'frontend/insights_list.html'
    context_object_name = 'articles'

    def get_queryset(self):
        return Article.objects.filter(status=Article.PUBLISHED).order_by('-published_at')


class ArticleDetailView(DetailView):
    template_name = 'frontend/article_detail.html'
    context_object_name = 'article'
    model = Article

    def get_object(self, queryset=None):
        article = super().get_object(queryset)
        if article.status != Article.PUBLISHED and not self.request.user.is_staff:
            raise Http404
        return article


def robots_txt(request):
    lines = [
        'User-agent: *',
        'Disallow: /admin/',
        'Disallow: /api/',
        '',
        f'Sitemap: {settings.SITE_URL}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain')


def sitemap_xml(request):
    names = ['home', 'analysis', 'exchange-rates', 'price-log', 'methodology',
             'about', 'contact', 'privacy-policy', 'terms']
    entries = [(reverse(name), None) for name in names]
    articles = Article.objects.filter(status=Article.PUBLISHED)
    if articles.exists():
        entries.append((reverse('insights'), None))
        entries += [(a.get_absolute_url(), a.updated_at.date().isoformat()) for a in articles]

    urls = []
    for path, lastmod in entries:
        when = f'<lastmod>{lastmod}</lastmod>' if lastmod else ''
        urls.append(f'<url><loc>{escape(settings.SITE_URL + path)}</loc>{when}</url>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + ''.join(urls) + '</urlset>\n')
    return HttpResponse(xml, content_type='application/xml')

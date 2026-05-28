"""
Fetch news from Sri Lankan RSS feeds and store in NewsArticle model.
Uses requests + ElementTree (no feedparser dependency).
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Country, NewsArticle


class Command(BaseCommand):
    help = "Fetch news articles from RSS feeds"

    def handle(self, *args, **options):
        # Google News RSS for Sri Lanka economy (reliable, no IP blocking)
        feeds = [
            ('https://news.google.com/rss/search?q=Sri+Lanka+economy+inflation&hl=en-US&gl=US&ceid=US:en', 'Google News'),
        ]

        lka = Country.objects.filter(code='LKA').first()
        created_count = 0
        skipped_count = 0

        for url, source_name in feeds:
            self.stdout.write(f"Fetching {source_name}...")
            try:
                resp = requests.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8',
                }, timeout=30)
                resp.raise_for_status()
                # Ada Derana uses ISO-8859-1; try UTF-8 first, fallback
                try:
                    content = resp.content.decode('utf-8')
                except UnicodeDecodeError:
                    content = resp.content.decode('iso-8859-1', errors='replace')

                root = ET.fromstring(content.encode('utf-8'))

                # Handle RSS 2.0 and Atom formats
                channel = root.find('channel')
                if channel is not None:
                    items = channel.findall('item')
                else:
                    # Atom
                    ns = {'atom': 'http://www.w3.org/2005/Atom'}
                    items = root.findall('atom:entry', ns)

                for item in items[:10]:
                    title = self._get_text(item, 'title')
                    link = self._get_text(item, 'link')
                    desc = self._get_text(item, 'description') or self._get_text(item, 'summary')
                    pub_date = self._get_text(item, 'pubDate') or self._get_text(item, 'published') or self._get_text(item, 'date')

                    if not title or not link:
                        continue

                    # Skip if already exists
                    if NewsArticle.objects.filter(source_url=link).exists():
                        skipped_count += 1
                        continue

                    # Parse date
                    published_at = self._parse_date(pub_date)

                    NewsArticle.objects.create(
                        country=lka,
                        title=title[:255],
                        summary=(desc or '')[:500],
                        source_url=link[:500],
                        source_name=source_name,
                        published_at=published_at or timezone.now(),
                    )
                    created_count += 1

                self.stdout.write(self.style.SUCCESS(f"  {source_name}: processed"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  {source_name} failed: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created_count}, Skipped (duplicates): {skipped_count}"
            )
        )

    def _get_text(self, item, tag):
        elem = item.find(tag)
        if elem is not None and elem.text:
            # Strip HTML tags
            text = re.sub(r'<[^>]+>', '', elem.text)
            return text.strip()
        return ''

    def _parse_date(self, date_str):
        if not date_str:
            return None
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S %Z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

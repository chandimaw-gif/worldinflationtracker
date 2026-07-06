"""
Management command: fetch_youtube_videos

Searches YouTube Data API v3 for recent videos about Sri Lanka inflation
and economy, stores them in the YouTubeVideo model for display on homepage.

Usage:
    python3 manage.py fetch_youtube_videos
    python3 manage.py fetch_youtube_videos --max 6
    python3 manage.py fetch_youtube_videos --dry-run
"""

import logging
from datetime import datetime, timedelta

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from core.models import Country, YouTubeVideo

logger = logging.getLogger('scrapers')

YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'
YOUTUBE_VIDEOS_URL = 'https://www.googleapis.com/youtube/v3/videos'

SEARCH_QUERIES = [
    'Sri Lanka inflation economy 2026',
    'Sri Lanka CBSL monetary policy 2026',
    'Sri Lanka rupee exchange rate 2026',
    'Sri Lanka cost of living prices 2026',
    'Sri Lanka economic crisis recovery',
]


class Command(BaseCommand):
    help = 'Fetch YouTube videos about Sri Lanka economy/inflation'

    def add_arguments(self, parser):
        parser.add_argument('--max', type=int, default=6,
                            help='Maximum videos to store (default 6)')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--api-key', type=str,
                            help='YouTube Data API key (overrides settings)')

    def handle(self, *args, **options):
        api_key = (options.get('api_key') or
                   getattr(settings, 'YOUTUBE_API_KEY', ''))
        if not api_key:
            self.stderr.write(self.style.ERROR(
                "No API key. Set YOUTUBE_API_KEY in settings."
            ))
            return

        try:
            country = Country.objects.get(code='LKA', is_active=True)
        except Country.DoesNotExist:
            self.stderr.write(self.style.ERROR("Country LKA not found"))
            return

        max_videos = options.get('max', 6)
        self.stdout.write(f"Searching YouTube for Sri Lanka economy videos...")

        all_video_ids = []
        seen_ids = set()

        for query in SEARCH_QUERIES:
            if len(all_video_ids) >= max_videos * 2:
                break
            try:
                params = {
                    'part': 'snippet',
                    'q': query,
                    'type': 'video',
                    'relevanceLanguage': 'en',
                    'order': 'relevance',
                    'maxResults': 5,
                    'publishedAfter': (
                        datetime.utcnow() - timedelta(days=180)
                    ).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'key': api_key,
                }
                r = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=15)
                r.raise_for_status()
                data = r.json()

                for item in data.get('items', []):
                    vid_id = item['id'].get('videoId')
                    if vid_id and vid_id not in seen_ids:
                        seen_ids.add(vid_id)
                        all_video_ids.append({
                            'id': vid_id,
                            'title': item['snippet']['title'],
                            'channel': item['snippet']['channelTitle'],
                            'published': item['snippet']['publishedAt'],
                            'thumbnail': (
                                item['snippet']['thumbnails']
                                .get('medium', {})
                                .get('url', '')
                            ),
                            'description': item['snippet'].get('description', '')[:300],
                        })

                self.stdout.write(
                    f"  '{query}': {len(data.get('items', []))} results"
                )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Query failed: {e}"))

        # Get view counts and duration for the top candidates
        if not all_video_ids:
            self.stderr.write(self.style.ERROR("No videos found"))
            return

        # Fetch video details (views, duration) for ranking
        ids_to_fetch = [v['id'] for v in all_video_ids[:20]]
        try:
            params = {
                'part': 'statistics,contentDetails',
                'id': ','.join(ids_to_fetch),
                'key': api_key,
            }
            r = requests.get(YOUTUBE_VIDEOS_URL, params=params, timeout=15)
            r.raise_for_status()
            details = {
                item['id']: item
                for item in r.json().get('items', [])
            }
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not fetch video details: {e}"))
            details = {}

        # Score and rank videos
        def score_video(v):
            detail = details.get(v['id'], {})
            stats = detail.get('statistics', {})
            views = int(stats.get('viewCount', 0))
            # Prefer recent, high-view videos about SL economy
            sl_keywords = ['sri lanka', 'lanka', 'cbsl', 'lkr', 'rupee', 'colombo']
            title_lower = v['title'].lower()
            sl_score = sum(2 for kw in sl_keywords if kw in title_lower)
            return views + sl_score * 10000

        all_video_ids.sort(key=score_video, reverse=True)
        top_videos = all_video_ids[:max_videos]

        if options.get('dry_run'):
            for v in top_videos:
                self.stdout.write(f"  [DRY RUN] {v['title'][:60]} ({v['channel']})")
            return

        # Save to database
        saved = 0
        # Clear old videos first
        YouTubeVideo.objects.filter(country=country).delete()

        for rank, v in enumerate(top_videos):
            detail = details.get(v['id'], {})
            stats = detail.get('statistics', {})

            published_dt = None
            try:
                published_dt = datetime.strptime(
                    v['published'], '%Y-%m-%dT%H:%M:%SZ'
                ).replace(tzinfo=timezone.utc)
            except Exception:
                pass

            try:
                YouTubeVideo.objects.create(
                    country=country,
                    video_id=v['id'],
                    title=v['title'],
                    channel_name=v['channel'],
                    thumbnail_url=v['thumbnail'],
                    description=v['description'],
                    view_count=int(stats.get('viewCount', 0)),
                    published_at=published_dt,
                    display_order=rank,
                )
                saved += 1
                self.stdout.write(f"  Saved: {v['title'][:60]}")
            except Exception as e:
                logger.error(f"Failed to save video {v['id']}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Saved {saved} YouTube videos."
        ))

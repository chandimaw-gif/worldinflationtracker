"""
Management command: fetch_youtube_videos

Fetches YouTube videos for the homepage using configured YouTubeSource entries.
If no active YouTubeSource entries exist, falls back to built-in search queries.

Usage:
    python3 manage.py fetch_youtube_videos
    python3 manage.py fetch_youtube_videos --max 6
    python3 manage.py fetch_youtube_videos --dry-run
    python3 manage.py fetch_youtube_videos --source "CBSL"
"""

import logging
from datetime import date, datetime, timedelta

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from core.models import Country, YouTubeVideo, YouTubeSource

logger = logging.getLogger('scrapers')

YOUTUBE_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'
YOUTUBE_VIDEOS_URL = 'https://www.googleapis.com/youtube/v3/videos'
YOUTUBE_CHANNEL_SEARCH_URL = 'https://www.googleapis.com/youtube/v3/search'

DEFAULT_SEARCH_QUERIES = [
    'Sri Lanka inflation economy 2026',
    'Sri Lanka CBSL monetary policy 2026',
    'Sri Lanka rupee exchange rate 2026',
    'Sri Lanka cost of living prices 2026',
    'Sri Lanka economic crisis recovery',
]


def _should_run_today(source):
    """Return True if the source's schedule says it should run today."""
    today = date.today()
    weekday = today.weekday()
    day_of_month = today.day

    freq = source.refresh_frequency
    if freq == 'daily':
        return True
    if freq == 'weekly':
        target = source.refresh_day_of_week
        return target is None or target == weekday
    if freq == 'monthly':
        target = source.refresh_day_of_month or 1
        return day_of_month == target
    return True


class Command(BaseCommand):
    help = 'Fetch YouTube videos from configured sources'

    def add_arguments(self, parser):
        parser.add_argument('--max', type=int, default=6,
                            help='Maximum videos to store (default 6)')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--api-key', type=str,
                            help='YouTube Data API key (overrides settings)')
        parser.add_argument('--source', type=str,
                            help='Only run a specific YouTubeSource by name')
        parser.add_argument('--force', action='store_true',
                            help='Ignore schedule and run all active sources')

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

        # Build list of sources to fetch
        sources = YouTubeSource.objects.filter(country=country, is_active=True)
        if options.get('source'):
            sources = sources.filter(name__icontains=options['source'])

        if sources.exists() and not options.get('force'):
            sources = [s for s in sources if _should_run_today(s)]

        use_default = not sources and not options.get('source')

        all_video_ids = []
        seen_ids = set()

        if use_default:
            self.stdout.write("No active YouTubeSource entries; using default queries.")
            queries = [{'name': 'Default', 'type': 'search', 'query': q, 'max_results': 5}
                       for q in DEFAULT_SEARCH_QUERIES]
        else:
            queries = [{
                'name': s.name,
                'type': s.source_type,
                'query': s.query,
                'max_results': s.max_results,
                'source_obj': s,
            } for s in sources]

        for source in queries:
            if len(all_video_ids) >= max_videos * 3:
                break
            try:
                if source['type'] == 'channel':
                    params = {
                        'part': 'snippet',
                        'channelId': source['query'],
                        'type': 'video',
                        'order': 'date',
                        'maxResults': source['max_results'],
                        'key': api_key,
                    }
                else:
                    params = {
                        'part': 'snippet',
                        'q': source['query'],
                        'type': 'video',
                        'relevanceLanguage': 'en',
                        'order': 'relevance',
                        'maxResults': source['max_results'],
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
                    f"  '{source['name']}': {len(data.get('items', []))} results"
                )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Source failed: {e}"))
                if source.get('source_obj'):
                    s = source['source_obj']
                    s.last_status = 'failed'
                    s.last_error = str(e)[:500]
                    s.last_fetched_at = timezone.now()
                    s.save(update_fields=['last_status', 'last_error', 'last_fetched_at'])

        if not all_video_ids:
            self.stderr.write(self.style.ERROR("No videos found"))
            return

        # Fetch video details (views) for ranking
        ids_to_fetch = [v['id'] for v in all_video_ids[:30]]
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

        def score_video(v):
            detail = details.get(v['id'], {})
            stats = detail.get('statistics', {})
            views = int(stats.get('viewCount', 0))
            sl_keywords = ['sri lanka', 'lanka', 'cbsl', 'lkr', 'rupee', 'colombo', 'inflation']
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

        # Update source statuses
        now = timezone.now()
        for source in queries:
            if source.get('source_obj'):
                s = source['source_obj']
                s.last_status = 'success'
                s.last_error = ''
                s.last_fetched_at = now
                s.save(update_fields=['last_status', 'last_error', 'last_fetched_at'])

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Saved {saved} YouTube videos."
        ))

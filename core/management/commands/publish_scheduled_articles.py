"""Publish finished drafts whose publish_on date has arrived. Run daily from cron."""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Article


class Command(BaseCommand):
    help = "Publish draft articles whose publish_on date has arrived."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report what is due without changing anything.')

    def handle(self, *args, **options):
        today = timezone.localdate()
        due = Article.objects.filter(status=Article.DRAFT, publish_on__lte=today)
        failed = []
        for article in due:
            article.status = Article.PUBLISHED
            try:
                article.full_clean()
            except ValidationError as exc:
                failed.append(article.slug)
                self.stderr.write(f"{today} NOT published {article.slug}: {exc}")
                continue
            if options['dry_run']:
                self.stdout.write(f"{today} due, would publish {article.slug}")
                continue
            article.save()
            self.stdout.write(f"{today} published {article.slug}")
        if failed:
            raise CommandError(f"Not published: {', '.join(failed)}")

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='YouTubeVideo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('video_id', models.CharField(max_length=20, unique=True)),
                ('title', models.CharField(max_length=500)),
                ('channel_name', models.CharField(max_length=200)),
                ('thumbnail_url', models.URLField(blank=True, max_length=500)),
                ('description', models.TextField(blank=True)),
                ('view_count', models.BigIntegerField(default=0)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='youtube_videos', to='core.country')),
            ],
            options={
                'verbose_name_plural': 'YouTube Videos',
                'ordering': ['display_order', '-view_count'],
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_new_tables_utf8mb4'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='publish_on',
            field=models.DateField(blank=True, help_text='Optional. A finished draft goes live at about 8:00 am Sri Lanka time on this date. Clear it to cancel.', null=True),
        ),
    ]

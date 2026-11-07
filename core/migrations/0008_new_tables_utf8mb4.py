from django.db import migrations

# The database defaults to latin1, which rejects most non-English text. These new
# tables hold free text from visitors and from the owner, so they use utf8mb4.
TABLES = ['core_article', 'core_monthlycommentary', 'core_contactmessage']


def convert(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    for table in TABLES:
        schema_editor.execute(f'ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_new_content_models'),
    ]

    operations = [
        migrations.RunPython(convert, migrations.RunPython.noop),
    ]

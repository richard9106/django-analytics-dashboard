from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_clientdocument_content_type_clientdocument_file_size_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientdocument',
            name='external_storage_provider',
            field=models.CharField(choices=[('none', 'None'), ('google_drive', 'Google Drive')], default='none', max_length=30),
        ),
        migrations.AddField(
            model_name='clientdocument',
            name='external_file_id',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='clientdocument',
            name='external_file_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='clientdocument',
            name='external_synced_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='clientdocument',
            name='external_sync_status',
            field=models.CharField(choices=[('not_synced', 'Not Synced'), ('pending', 'Pending'), ('synced', 'Synced'), ('failed', 'Failed'), ('disabled', 'Disabled')], default='not_synced', max_length=20),
        ),
        migrations.AddField(
            model_name='clientdocument',
            name='external_sync_error',
            field=models.TextField(blank=True),
        ),
    ]

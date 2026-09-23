from django.db import migrations, models


def migrate_legacy_google_rows(apps, schema_editor):
    ExternalIntegration = apps.get_model('practices', 'ExternalIntegration')
    for integration in ExternalIntegration.objects.filter(provider='gmail'):
        google, created = ExternalIntegration.objects.get_or_create(
            practice=integration.practice,
            provider='google',
            defaults={
                'status': integration.status,
                'account_email': integration.account_email,
                'send_email_enabled': integration.send_email_enabled,
                'read_email_enabled': integration.read_email_enabled,
                'default_folder': integration.default_folder,
                'notes': integration.notes,
                'connected_at': integration.connected_at,
            },
        )
        if not created:
            google.send_email_enabled = google.send_email_enabled or integration.send_email_enabled
            google.read_email_enabled = google.read_email_enabled or integration.read_email_enabled
            google.save()
    for integration in ExternalIntegration.objects.filter(provider='google_drive'):
        google, created = ExternalIntegration.objects.get_or_create(
            practice=integration.practice,
            provider='google',
            defaults={
                'status': integration.status,
                'account_email': integration.account_email,
                'file_storage_enabled': integration.file_storage_enabled,
                'default_folder': integration.default_folder,
                'notes': integration.notes,
                'connected_at': integration.connected_at,
            },
        )
        if not created:
            google.file_storage_enabled = google.file_storage_enabled or integration.file_storage_enabled
            google.save()


class Migration(migrations.Migration):

    dependencies = [
        ('practices', '0002_externalintegration'),
    ]

    operations = [
        migrations.AddField(
            model_name='externalintegration',
            name='access_token',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='externalintegration',
            name='calendar_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='externalintegration',
            name='enabled_scopes',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='externalintegration',
            name='granted_scopes',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='externalintegration',
            name='oauth_state',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='externalintegration',
            name='refresh_token',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='externalintegration',
            name='token_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(migrate_legacy_google_rows, migrations.RunPython.noop),
    ]

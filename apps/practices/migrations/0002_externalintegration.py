from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('practices', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('gmail', 'Gmail'), ('google_drive', 'Google Drive'), ('dropbox', 'Dropbox')], max_length=30)),
                ('status', models.CharField(choices=[('disconnected', 'Disconnected'), ('connected', 'Connected'), ('needs_reauth', 'Needs reauthorization')], default='disconnected', max_length=30)),
                ('account_email', models.EmailField(blank=True, max_length=254)),
                ('send_email_enabled', models.BooleanField(default=False)),
                ('read_email_enabled', models.BooleanField(default=False)),
                ('file_storage_enabled', models.BooleanField(default=False)),
                ('default_folder', models.CharField(blank=True, max_length=180)),
                ('notes', models.TextField(blank=True)),
                ('connected_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='external_integrations', to='practices.practice')),
            ],
            options={'ordering': ['provider']},
        ),
        migrations.AddConstraint(
            model_name='externalintegration',
            constraint=models.UniqueConstraint(fields=('practice', 'provider'), name='unique_external_integration_per_practice_provider'),
        ),
    ]

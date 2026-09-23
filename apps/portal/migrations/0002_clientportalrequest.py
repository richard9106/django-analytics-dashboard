from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0001_initial'),
        ('practices', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portal', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientPortalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('reschedule', 'I need to reschedule'), ('billing', 'Billing question'), ('document', 'Document question'), ('general', 'General message')], max_length=30)),
                ('subject', models.CharField(max_length=160)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('new', 'New'), ('reviewed', 'Reviewed'), ('resolved', 'Resolved')], default='new', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='portal_requests', to='clients.client')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='portal_requests', to='practices.practice')),
                ('submitted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='portal_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='reminder_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='appointment',
            name='reminder_status',
            field=models.CharField(choices=[('not_scheduled', 'Not Scheduled'), ('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('disabled', 'Disabled')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='appointment',
            name='reminder_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='appointment',
            name='reminder_error',
            field=models.TextField(blank=True),
        ),
    ]

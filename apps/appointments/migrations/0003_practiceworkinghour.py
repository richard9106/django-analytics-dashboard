import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0002_appointment_reminder_fields'),
        ('practices', '0005_encrypt_externalintegration_tokens'),
    ]

    operations = [
        migrations.CreateModel(
            name='PracticeWorkingHour',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.PositiveSmallIntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('starts_at', models.TimeField()),
                ('ends_at', models.TimeField()),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='working_hours', to='practices.practice')),
            ],
            options={'ordering': ['weekday', 'starts_at']},
        ),
    ]

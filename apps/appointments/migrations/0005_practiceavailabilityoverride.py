from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0004_appointment_series_id'),
        ('practices', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PracticeAvailabilityOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('starts_at', models.TimeField(blank=True, null=True)),
                ('ends_at', models.TimeField(blank=True, null=True)),
                ('is_available', models.BooleanField(default=True)),
                ('note', models.CharField(blank=True, max_length=160)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='availability_overrides', to='practices.practice')),
            ],
            options={
                'ordering': ['date', 'starts_at', 'ends_at'],
            },
        ),
    ]

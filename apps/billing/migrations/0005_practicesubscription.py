import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_insurancepayer_insurancerate'),
        ('practices', '0005_encrypt_externalintegration_tokens'),
    ]

    operations = [
        migrations.CreateModel(
            name='PracticeSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan', models.CharField(choices=[('solo', 'Solo Therapist'), ('group', 'Group Practice'), ('clinic', 'Clinic')], max_length=20)),
                ('billing_period', models.CharField(choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')], max_length=20)),
                ('status', models.CharField(choices=[('incomplete', 'Incomplete'), ('active', 'Active'), ('past_due', 'Past Due'), ('canceled', 'Canceled'), ('unpaid', 'Unpaid')], default='incomplete', max_length=20)),
                ('stripe_customer_id', models.CharField(blank=True, max_length=120)),
                ('stripe_subscription_id', models.CharField(blank=True, max_length=120)),
                ('stripe_price_id', models.CharField(blank=True, max_length=120)),
                ('current_period_end', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to='practices.practice')),
            ],
            options={'ordering': ['practice__name']},
        ),
    ]

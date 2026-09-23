from django.db import migrations, models
import django.db.models.deletion


COMMON_PAYERS = [
    'Aetna',
    'Anthem Blue Cross Blue Shield',
    'Blue Cross Blue Shield',
    'Carelon Behavioral Health',
    'Cigna / Evernorth',
    'Humana',
    'Kaiser Permanente',
    'Medicaid',
    'Medicare',
    'Molina Healthcare',
    'Oscar Health',
    'TRICARE',
    'UnitedHealthcare / Optum',
]


def seed_common_payers(apps, schema_editor):
    InsurancePayer = apps.get_model('billing', 'InsurancePayer')
    for name in COMMON_PAYERS:
        InsurancePayer.objects.get_or_create(
            practice=None,
            name=name,
            defaults={'is_system_template': True, 'active': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('practices', '0001_initial'),
        ('billing', '0003_sessionpackagetemplate_servicepackage_template_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='InsurancePayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=140)),
                ('payer_id', models.CharField(blank=True, max_length=80)),
                ('is_system_template', models.BooleanField(default=False)),
                ('active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='insurance_payers', to='practices.practice')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='InsuranceRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(max_length=2)),
                ('service_code', models.CharField(choices=[('90791', '90791 - Psychiatric diagnostic evaluation'), ('90834', '90834 - Psychotherapy, 45 minutes'), ('90837', '90837 - Psychotherapy, 60 minutes'), ('90847', '90847 - Family psychotherapy'), ('90853', '90853 - Group psychotherapy'), ('90839', '90839 - Psychotherapy for crisis'), ('other', 'Other')], max_length=20)),
                ('service_label', models.CharField(blank=True, max_length=160)),
                ('reimbursement_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('payer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rates', to='billing.insurancepayer')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='insurance_rates', to='practices.practice')),
            ],
            options={'ordering': ['state', 'payer__name', 'service_code']},
        ),
        migrations.AddConstraint(
            model_name='insurancepayer',
            constraint=models.UniqueConstraint(fields=('practice', 'name'), name='unique_insurance_payer_per_practice'),
        ),
        migrations.AddConstraint(
            model_name='insurancerate',
            constraint=models.UniqueConstraint(fields=('practice', 'payer', 'state', 'service_code'), name='unique_insurance_rate_per_state_service'),
        ),
        migrations.RunPython(seed_common_payers, migrations.RunPython.noop),
    ]

import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0001_initial'),
        ('clinical', '0001_initial'),
        ('practices', '0005_encrypt_externalintegration_tokens'),
    ]

    operations = [
        migrations.CreateModel(
            name='Diagnosis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20)),
                ('label', models.CharField(max_length=180)),
                ('diagnosed_at', models.DateField(default=django.utils.timezone.localdate)),
                ('active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diagnoses', to='clients.client')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diagnoses', to='practices.practice')),
            ],
            options={'ordering': ['-diagnosed_at', 'code']},
        ),
        migrations.CreateModel(
            name='TreatmentPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=160)),
                ('status', models.CharField(choices=[('active', 'Active'), ('review_due', 'Review Due'), ('completed', 'Completed'), ('discontinued', 'Discontinued')], default='active', max_length=20)),
                ('goals', models.TextField()),
                ('objectives', models.TextField(blank=True)),
                ('interventions', models.TextField(blank=True)),
                ('start_date', models.DateField(default=django.utils.timezone.localdate)),
                ('review_date', models.DateField(blank=True, null=True)),
                ('completed_at', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='treatment_plans', to='clients.client')),
                ('diagnoses', models.ManyToManyField(blank=True, related_name='treatment_plans', to='clinical.diagnosis')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='treatment_plans', to='practices.practice')),
                ('therapist', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='treatment_plans', to='practices.therapistprofile')),
            ],
            options={'ordering': ['-start_date', 'client__last_name']},
        ),
        migrations.AddConstraint(
            model_name='diagnosis',
            constraint=models.UniqueConstraint(fields=('practice', 'client', 'code'), name='unique_diagnosis_code_per_client'),
        ),
    ]

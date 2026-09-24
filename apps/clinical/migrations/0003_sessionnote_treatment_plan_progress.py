import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinical', '0002_diagnosis_treatmentplan'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionnote',
            name='treatment_plan',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='session_notes', to='clinical.treatmentplan'),
        ),
        migrations.AddField(
            model_name='sessionnote',
            name='treatment_progress',
            field=models.TextField(blank=True),
        ),
    ]

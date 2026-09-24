import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0002_appointment_reminder_fields'),
        ('portal', '0005_intakepackettemplate_clientintakeassignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientportalrequest',
            name='appointment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='portal_requests', to='appointments.appointment'),
        ),
    ]

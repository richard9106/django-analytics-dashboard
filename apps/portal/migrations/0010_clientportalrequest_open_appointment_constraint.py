from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('portal', '0009_portalmessage_read_at')]

    operations = [
        migrations.AddConstraint(
            model_name='clientportalrequest',
            constraint=models.UniqueConstraint(
                fields=('appointment',),
                condition=Q(appointment__isnull=False, status__in=['new', 'reviewed']),
                name='one_open_change_request_per_appointment',
            ),
        ),
    ]

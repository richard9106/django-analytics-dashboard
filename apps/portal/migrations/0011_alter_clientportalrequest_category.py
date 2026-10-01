from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portal', '0010_clientportalrequest_open_appointment_constraint')]

    operations = [
        migrations.AlterField(
            model_name='clientportalrequest',
            name='category',
            field=models.CharField(
                choices=[
                    ('reschedule', 'I need to reschedule'),
                    ('cancellation', 'I need to cancel'),
                    ('billing', 'Billing question'),
                    ('document', 'Document question'),
                    ('general', 'General message'),
                ],
                max_length=30,
            ),
        ),
    ]

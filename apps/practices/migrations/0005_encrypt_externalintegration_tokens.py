import apps.practices.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('practices', '0004_alter_externalintegration_provider'),
    ]

    operations = [
        migrations.AlterField(
            model_name='externalintegration',
            name='access_token',
            field=apps.practices.fields.EncryptedTextField(blank=True),
        ),
        migrations.AlterField(
            model_name='externalintegration',
            name='refresh_token',
            field=apps.practices.fields.EncryptedTextField(blank=True),
        ),
    ]

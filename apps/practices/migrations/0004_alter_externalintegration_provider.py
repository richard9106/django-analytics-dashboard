from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('practices', '0003_google_oauth_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='externalintegration',
            name='provider',
            field=models.CharField(choices=[('google', 'Google'), ('dropbox', 'Dropbox')], max_length=30),
        ),
    ]

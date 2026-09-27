from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_practicesubscription'),
    ]

    operations = [
        migrations.AlterField(
            model_name='practicesubscription',
            name='status',
            field=models.CharField(choices=[('incomplete', 'Incomplete'), ('trialing', 'Trialing'), ('active', 'Active'), ('past_due', 'Past Due'), ('canceled', 'Canceled'), ('unpaid', 'Unpaid')], default='incomplete', max_length=20),
        ),
    ]

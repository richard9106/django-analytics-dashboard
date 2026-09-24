import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('clients', '0001_initial'),
        ('portal', '0002_clientportalrequest'),
        ('practices', '0005_encrypt_externalintegration_tokens'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntakePacketTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=160)),
                ('description', models.TextField(blank=True)),
                ('questions', models.JSONField(blank=True, default=list)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='intake_templates', to='practices.practice')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='ClientIntakeAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('assigned', 'Assigned'), ('submitted', 'Submitted'), ('reviewed', 'Reviewed')], default='assigned', max_length=20)),
                ('answers', models.JSONField(blank=True, default=dict)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_intakes', to=settings.AUTH_USER_MODEL)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='intake_assignments', to='clients.client')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='intake_assignments', to='practices.practice')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_intakes', to=settings.AUTH_USER_MODEL)),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignments', to='portal.intakepackettemplate')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='intakepackettemplate',
            constraint=models.UniqueConstraint(fields=('practice', 'name'), name='unique_intake_template_name_per_practice'),
        ),
    ]

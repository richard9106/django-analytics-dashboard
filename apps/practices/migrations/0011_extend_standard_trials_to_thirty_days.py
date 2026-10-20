from datetime import timedelta
from django.db import migrations


def extend_standard_trials(apps, schema_editor):
    Practice = apps.get_model('practices', 'Practice')
    for practice in Practice.objects.filter(free_access_kind='trial', free_trial_started_at__isnull=False).exclude(subscription__status__in=['active', 'trialing', 'past_due', 'unpaid']).iterator():
        if practice.free_trial_ends_at == practice.free_trial_started_at + timedelta(days=15):
            Practice.objects.filter(pk=practice.pk).update(free_trial_ends_at=practice.free_trial_started_at + timedelta(days=30))


class Migration(migrations.Migration):
    dependencies = [('practices', '0010_practice_free_access_kind_earlyaccessinvitation'), ('billing', '0012_practicesubscription_cancellation_access_until')]
    operations = [migrations.RunPython(extend_standard_trials, migrations.RunPython.noop)]

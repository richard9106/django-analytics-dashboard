from django.db import migrations


def preserve(apps, schema_editor):
    Rate = apps.get_model('billing', 'InsuranceRate')
    Selection = apps.get_model('billing', 'PracticeInsurancePayer')
    for practice_id, payer_id in Rate.objects.filter(payer__practice__isnull=True).values_list('practice_id', 'payer_id').distinct():
        Selection.objects.get_or_create(practice_id=practice_id, payer_id=payer_id, defaults={'active': True})


class Migration(migrations.Migration):
    dependencies = [('billing', '0013_practice_insurance_workflow')]
    operations = [migrations.RunPython(preserve, migrations.RunPython.noop)]

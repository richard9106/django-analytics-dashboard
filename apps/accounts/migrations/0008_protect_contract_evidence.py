from django.db import migrations

TABLES = ('accounts_clinicalcontractrequest', 'accounts_clinicalcontractbundle',
          'accounts_clinicalcontractsignature')


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute("""
        CREATE FUNCTION nuviamy_reject_contract_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Contract evidence cannot be changed or deleted.' USING ERRCODE = '23514';
        END;
        $$;
    """)
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER contract_reject_mutation BEFORE UPDATE OR DELETE ON {table} '
                              'FOR EACH ROW EXECUTE FUNCTION nuviamy_reject_contract_mutation();')
        schema_editor.execute(f'CREATE TRIGGER contract_reject_truncate BEFORE TRUNCATE ON {table} '
                              'FOR EACH STATEMENT EXECUTE FUNCTION nuviamy_reject_contract_mutation();')


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for table in TABLES:
        schema_editor.execute(f'DROP TRIGGER contract_reject_truncate ON {table};')
        schema_editor.execute(f'DROP TRIGGER contract_reject_mutation ON {table};')
    schema_editor.execute('DROP FUNCTION nuviamy_reject_contract_mutation();')


class Migration(migrations.Migration):
    dependencies = [('accounts', '0007_clinical_contract_evidence')]
    operations = [migrations.RunPython(protect, unprotect)]

from django.db import migrations


SQL = """
CREATE FUNCTION nuviamy_protect_finalized_note() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.is_locked THEN
        RAISE EXCEPTION 'Finalized clinical notes cannot be changed or deleted.' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER clinical_protect_finalized BEFORE UPDATE OR DELETE ON clinical_sessionnote
    FOR EACH ROW EXECUTE FUNCTION nuviamy_protect_finalized_note();
CREATE FUNCTION nuviamy_reject_note_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Clinical notes cannot be truncated.' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER clinical_reject_truncate BEFORE TRUNCATE ON clinical_sessionnote
    FOR EACH STATEMENT EXECUTE FUNCTION nuviamy_reject_note_truncate();
"""
REVERSE_SQL = """
DROP TRIGGER clinical_reject_truncate ON clinical_sessionnote;
DROP TRIGGER clinical_protect_finalized ON clinical_sessionnote;
DROP FUNCTION nuviamy_reject_note_truncate();
DROP FUNCTION nuviamy_protect_finalized_note();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(SQL)


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [('clinical', '0004_alter_diagnosis_client_alter_diagnosis_practice_and_more')]
    operations = [migrations.RunPython(protect, unprotect)]

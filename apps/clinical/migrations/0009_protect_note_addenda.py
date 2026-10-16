from django.db import migrations

SQL = """
CREATE FUNCTION nuviamy_protect_note_addendum() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Signed addenda are immutable.' USING ERRCODE = '23514';
    END IF;
    IF btrim(NEW.reason) = '' OR btrim(NEW.content) = '' OR NOT EXISTS (
        SELECT 1 FROM clinical_sessionnote n
        JOIN clinical_sessionnotesignature s ON s.note_id = n.id
        JOIN practices_therapistprofile t ON t.id = n.therapist_id
        WHERE n.id = NEW.note_id AND n.is_locked AND t.user_id = NEW.signed_by_id
          AND s.digest = NEW.original_digest
    ) THEN
        RAISE EXCEPTION 'Addenda require an original signed note and its responsible therapist.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER clinical_protect_addendum BEFORE INSERT OR UPDATE OR DELETE ON clinical_sessionnoteaddendum
FOR EACH ROW EXECUTE FUNCTION nuviamy_protect_note_addendum();
CREATE TRIGGER clinical_addendum_reject_truncate BEFORE TRUNCATE ON clinical_sessionnoteaddendum
FOR EACH STATEMENT EXECUTE FUNCTION nuviamy_protect_note_addendum();
"""
REVERSE = "DROP TRIGGER clinical_addendum_reject_truncate ON clinical_sessionnoteaddendum; DROP TRIGGER clinical_protect_addendum ON clinical_sessionnoteaddendum; DROP FUNCTION nuviamy_protect_note_addendum();"


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(SQL)


def unprotect(apps, schema_editor):
    if apps.get_model('clinical', 'SessionNoteAddendum').objects.exists():
        raise RuntimeError('Cannot remove addendum safeguards while signed addenda exist. Preserve the clinical history.')
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(REVERSE)


class Migration(migrations.Migration):
    dependencies = [('clinical', '0008_sessionnoteaddendum')]
    operations = [migrations.RunPython(protect, unprotect)]

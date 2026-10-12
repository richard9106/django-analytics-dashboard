from django.db import migrations

SQL = """
CREATE FUNCTION nuviamy_protect_note_signature() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Clinical signatures are immutable.' USING ERRCODE = '23514';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM clinical_sessionnote n JOIN practices_therapistprofile t ON t.id = n.therapist_id
        WHERE n.id = NEW.note_id AND n.is_locked AND t.user_id = NEW.signed_by_id
    ) THEN
        RAISE EXCEPTION 'The responsible therapist must sign a finalized note.' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER clinical_protect_signature BEFORE INSERT OR UPDATE OR DELETE ON clinical_sessionnotesignature
FOR EACH ROW EXECUTE FUNCTION nuviamy_protect_note_signature();
CREATE TRIGGER clinical_signature_reject_truncate BEFORE TRUNCATE ON clinical_sessionnotesignature
FOR EACH STATEMENT EXECUTE FUNCTION nuviamy_protect_note_signature();
"""
REVERSE = "DROP TRIGGER clinical_signature_reject_truncate ON clinical_sessionnotesignature; DROP TRIGGER clinical_protect_signature ON clinical_sessionnotesignature; DROP FUNCTION nuviamy_protect_note_signature();"

def protect(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql': schema_editor.execute(SQL)

def reverse(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql': schema_editor.execute(REVERSE)

class Migration(migrations.Migration):
    dependencies = [('clinical', '0006_sessionnotesignature')]
    operations = [migrations.RunPython(protect, reverse)]

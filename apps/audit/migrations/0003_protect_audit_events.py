from django.db import migrations


SQL = """

CREATE FUNCTION nuviamy_audit_actor_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.actor_id_snapshot := NEW.actor_id;
    NEW.actor_username_snapshot := COALESCE((SELECT username FROM auth_user WHERE id = NEW.actor_id), '');
    RETURN NEW;
END;
$$;
CREATE TRIGGER audit_capture_actor BEFORE INSERT ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION nuviamy_audit_actor_snapshot();

UPDATE audit_auditlog AS event SET actor_id_snapshot = event.actor_id,
    actor_username_snapshot = actor.username FROM auth_user AS actor
    WHERE event.actor_id = actor.id;


CREATE FUNCTION nuviamy_reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Audit events cannot be changed or deleted.' USING ERRCODE = '23514';
END;
$$;
CREATE TRIGGER audit_reject_mutation BEFORE UPDATE OR DELETE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION nuviamy_reject_audit_mutation();
CREATE TRIGGER audit_reject_truncate BEFORE TRUNCATE ON audit_auditlog
    FOR EACH STATEMENT EXECUTE FUNCTION nuviamy_reject_audit_mutation();
"""

REVERSE_SQL = """
DROP TRIGGER audit_reject_truncate ON audit_auditlog;
DROP TRIGGER audit_reject_mutation ON audit_auditlog;
DROP TRIGGER audit_capture_actor ON audit_auditlog;
DROP FUNCTION nuviamy_reject_audit_mutation();
DROP FUNCTION nuviamy_audit_actor_snapshot();
"""


def protect(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(SQL)
    else:
        Event = apps.get_model('audit', 'AuditLog')
        for event in Event.objects.using(schema_editor.connection.alias).exclude(actor=None).select_related('actor').iterator():
            event.actor_id_snapshot = event.actor_id
            event.actor_username_snapshot = event.actor.username
            event.save(update_fields=['actor_id_snapshot', 'actor_username_snapshot'])


def unprotect(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [('audit', '0002_auditlog_actor_id_snapshot_and_more')]
    operations = [migrations.RunPython(protect, unprotect)]

"""Provision/verify PostgreSQL roles without exposing credentials in command output."""
import argparse
import os
import re

import psycopg
from psycopg import sql
from dotenv import dotenv_values


CRUD = 'SELECT, INSERT, UPDATE, DELETE'
GUARDS = {'audit_capture_actor', 'audit_reject_mutation', 'audit_reject_truncate',
          'clinical_protect_finalized', 'clinical_reject_truncate'}


def identifier(value):
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', value or ''):
        raise ValueError('Dedicated database role names must be lowercase SQL identifiers.')
    return sql.Identifier(value)


def provision(conn, app, migrator, app_password, migration_password):
    app_id, migration_id = identifier(app), identifier(migrator)
    admin = conn.execute('SELECT current_user').fetchone()[0]
    if len({app, migrator, admin}) != 3:
        raise ValueError('Application, migration, and bootstrap roles must be distinct.')
    if (min(len(app_password), len(migration_password)) < 32 or app_password == migration_password
            or any(value.lower().startswith(('change-me', 'replace_')) for value in (app_password, migration_password))):
        raise ValueError('Dedicated role passwords must be distinct and at least 32 characters.')
    with conn.transaction():
        for name, role_id, password in [(app, app_id, app_password), (migrator, migration_id, migration_password)]:
            if conn.execute('SELECT 1 FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname = %s)', [name]).fetchone():
                raise ValueError('Dedicated roles must not have inherited role memberships.')
            if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', [name]).fetchone():
                conn.execute(sql.SQL('CREATE ROLE {}').format(role_id))
            # Only a SCRAM verifier, never the plaintext password, reaches SQL logging.
            verifier = conn.pgconn.encrypt_password(password.encode(), name.encode(), b'scram-sha-256').decode()
            conn.execute(sql.SQL('ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}').format(role_id, sql.Literal(verifier)))
        database = conn.execute('SELECT current_database()').fetchone()[0]
        conn.execute(sql.SQL('ALTER DATABASE {} OWNER TO {}').format(sql.Identifier(database), migration_id))
        conn.execute(sql.SQL('ALTER SCHEMA public OWNER TO {}').format(migration_id))
        # Transfer only this application's public objects, never cluster-wide REASSIGN OWNED.
        objects = conn.execute("SELECT c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S') AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=c.oid AND d.classid='pg_class'::regclass AND d.deptype='e') ORDER BY CASE WHEN c.relkind='S' THEN 1 ELSE 0 END").fetchall()
        for name, kind in objects:
            command = {'r': 'TABLE', 'p': 'TABLE', 'v': 'VIEW', 'm': 'MATERIALIZED VIEW', 'S': 'SEQUENCE'}[kind]
            conn.execute(sql.SQL('ALTER {} public.{} OWNER TO {}').format(sql.SQL(command), sql.Identifier(name), migration_id))
        functions = conn.execute("SELECT p.proname, pg_get_function_identity_arguments(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind='f' AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=p.oid AND d.classid='pg_proc'::regclass AND d.deptype='e')").fetchall()
        for name, arguments in functions:
            conn.execute(sql.SQL('ALTER FUNCTION public.{}({}) OWNER TO {}').format(sql.Identifier(name), sql.SQL(arguments), migration_id))
        grant_runtime(conn, app, migrator)


def grant_runtime(conn, app, migrator):
    app_id, migration_id = identifier(app), identifier(migrator)
    database = sql.Identifier(conn.execute('SELECT current_database()').fetchone()[0])
    with conn.transaction():
        conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC, {}').format(database, app_id))
        conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(database, app_id))
        conn.execute(sql.SQL('REVOKE ALL ON SCHEMA public FROM PUBLIC, {}').format(app_id))
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(app_id))
        conn.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, {}').format(app_id))
        conn.execute(sql.SQL('GRANT '+CRUD+' ON ALL TABLES IN SCHEMA public TO {}').format(app_id))
        if conn.execute("SELECT to_regclass('public.audit_auditlog')").fetchone()[0]:
            conn.execute(sql.SQL('REVOKE UPDATE, DELETE ON public.audit_auditlog FROM {}').format(app_id))
        if conn.execute("SELECT to_regclass('public.django_migrations')").fetchone()[0]:
            conn.execute(sql.SQL('REVOKE INSERT, UPDATE, DELETE ON public.django_migrations FROM {}').format(app_id))
        conn.execute(sql.SQL('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, {}').format(app_id))
        conn.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(app_id))
        conn.execute(sql.SQL('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, {}').format(app_id))
        for name in ['nuviamy_audit_actor_snapshot', 'nuviamy_reject_audit_mutation', 'nuviamy_protect_finalized_note', 'nuviamy_reject_note_truncate']:
            if conn.execute('SELECT to_regprocedure(%s)', ['public.' + name + '()']).fetchone()[0]:
                conn.execute(sql.SQL('GRANT EXECUTE ON FUNCTION public.{}() TO {}').format(sql.Identifier(name), app_id))
        conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT '+CRUD+' ON TABLES TO {}').format(migration_id, app_id))
        conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}').format(migration_id, app_id))
        conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC').format(migration_id))


def verify_runtime(conn):
    flags = conn.execute('SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
    if any(flags):
        raise ValueError('Runtime database role has administrative privileges.')
    if conn.execute('SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)').fetchone():
        raise ValueError('Runtime database role has role memberships.')
    if conn.execute("SELECT has_database_privilege(current_database(), 'CREATE') OR has_database_privilege(current_database(), 'TEMP') OR has_schema_privilege('public', 'CREATE')").fetchone()[0]:
        raise ValueError('Runtime database role can create database objects.')
    if conn.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user) UNION ALL SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)").fetchone():
        raise ValueError('Runtime role owns application database objects.')
    rows = conn.execute("SELECT relname, has_table_privilege(c.oid,'SELECT'), has_table_privilege(c.oid,'INSERT'), has_table_privilege(c.oid,'UPDATE'), has_table_privilege(c.oid,'DELETE'), has_table_privilege(c.oid,'TRUNCATE') OR has_table_privilege(c.oid,'TRIGGER') OR has_table_privilege(c.oid,'REFERENCES') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p')").fetchall()
    for name, read, insert, update, delete, elevated in rows:
        expected = (True, False, False, False) if name == 'django_migrations' else (True, True, False, False) if name == 'audit_auditlog' else (True, True, True, True)
        if (read, insert, update, delete) != expected or elevated:
            raise ValueError('Runtime table privileges differ from the required policy.')
    guards = dict(conn.execute('SELECT tgname, tgenabled FROM pg_trigger WHERE tgname=ANY(%s)', [list(GUARDS)]).fetchall())
    if set(guards) != GUARDS or any(value != 'O' for value in guards.values()):
        raise ValueError('Required audit/clinical guards are missing or disabled.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['bootstrap', 'grant', 'verify'])
    parser.add_argument('--env-file')
    args = parser.parse_args()
    env = dict(os.environ)
    if args.env_file:
        credential_keys = {'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD',
                           'POSTGRES_APP_USER', 'POSTGRES_APP_PASSWORD',
                           'POSTGRES_MIGRATION_USER', 'POSTGRES_MIGRATION_PASSWORD'}
        env.update({key: value for key, value in dotenv_values(args.env_file).items()
                    if key in credential_keys and value is not None})
    try:
        with psycopg.connect(host=env.get('POSTGRES_HOST', 'db'), port=env.get('POSTGRES_PORT', '5432'), dbname=env['POSTGRES_DB'], user=env['POSTGRES_USER'], password=env['POSTGRES_PASSWORD'], autocommit=True) as conn:
            if args.action == 'bootstrap':
                provision(conn, env['POSTGRES_APP_USER'], env['POSTGRES_MIGRATION_USER'], env['POSTGRES_APP_PASSWORD'], env['POSTGRES_MIGRATION_PASSWORD'])
            elif args.action == 'grant':
                grant_runtime(conn, env['POSTGRES_APP_USER'], env['POSTGRES_USER'])
            else:
                verify_runtime(conn)
        print('PostgreSQL role operation succeeded: ' + args.action)
    except (KeyError, ValueError, psycopg.Error):
        # Do not print connection details, SQL containing verifiers, or credentials.
        raise SystemExit('PostgreSQL role operation failed; review role configuration and database permissions.')


if __name__ == '__main__':
    main()

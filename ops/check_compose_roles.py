"""Check credential separation using fake configuration, without printing secrets."""
import json
import os
import subprocess
import tempfile
from pathlib import Path


def main():
    fixtures = {'POSTGRES_DB': 'nuviamy_fixture', 'POSTGRES_USER': 'bootstrap_fixture',
                'POSTGRES_PASSWORD': 'synthetic-bootstrap-secret-32-characters',
                'POSTGRES_APP_USER': 'app_fixture', 'POSTGRES_APP_PASSWORD': 'synthetic-app-secret-32-characters',
                'POSTGRES_MIGRATION_USER': 'migration_fixture', 'POSTGRES_MIGRATION_PASSWORD': 'synthetic-migration-secret-32-characters',
                'DJANGO_SECRET_KEY': 'synthetic-django-secret-that-is-long-enough-for-production',
                'FIELD_ENCRYPTION_KEY': 'MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA='}
    with tempfile.TemporaryDirectory() as directory:
        env_file = Path(directory) / 'fixture.env'
        env_file.write_text('\n'.join(key + '=' + value for key, value in fixtures.items()))
        configuration = json.loads(subprocess.check_output(['docker', 'compose', '--env-file', str(env_file), '--profile', 'maintenance', 'config', '--format', 'json'], env=dict(os.environ, **fixtures)))
        rehearsal = json.loads(subprocess.check_output(['docker', 'compose', '--env-file', str(env_file), '-f', 'docker-compose.yml', '-f', 'ops/aws/rehearsal.compose.yml', '--profile', 'maintenance', 'config', '--format', 'json'], env=dict(os.environ, **fixtures)))
        assert rehearsal['networks']['default']['internal'] is True
        for service in ('web','migrate'):
            isolated = rehearsal['services'][service]['environment']
            assert isolated['MIGRATION_REHEARSAL'] == 'true'
            assert isolated['AWS_EC2_METADATA_DISABLED'] == 'true'
            assert isolated['EMAIL_BACKEND'] == 'django.core.mail.backends.dummy.EmailBackend'
            for key in ('STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','GOOGLE_OAUTH_CLIENT_SECRET','AWS_ACCESS_KEY_ID','AWS_SESSION_TOKEN','DJANGO_STORAGE_BACKEND','SENTRY_DSN'):
                assert not isolated[key]
            assert rehearsal['services'][service]['image'] == 'nuviamy-rehearsal:local'

    services = configuration['services']
    assert services['db']['environment']['POSTGRES_USER'] == fixtures['POSTGRES_USER']
    assert services['db']['environment']['POSTGRES_PASSWORD'] == fixtures['POSTGRES_PASSWORD']
    assert services['web']['environment']['POSTGRES_USER'] == fixtures['POSTGRES_APP_USER']
    assert services['web']['environment']['POSTGRES_PASSWORD'] == fixtures['POSTGRES_APP_PASSWORD']
    assert not {'POSTGRES_MIGRATION_USER', 'POSTGRES_MIGRATION_PASSWORD', 'POSTGRES_APP_PASSWORD'} & set(services['web']['environment'])
    assert fixtures['POSTGRES_PASSWORD'] not in services['web']['environment'].values()
    assert fixtures['POSTGRES_MIGRATION_PASSWORD'] not in services['web']['environment'].values()
    assert services['migrate']['environment']['POSTGRES_USER'] == fixtures['POSTGRES_MIGRATION_USER']
    assert services['migrate']['environment']['POSTGRES_PASSWORD'] == fixtures['POSTGRES_MIGRATION_PASSWORD']
    assert services['migrate']['image'] == services['web']['image']
    assert services['migrate']['profiles'] == ['maintenance']
    assert not services['migrate'].get('ports')
    assert not services['migrate'].get('restart')
    print('Compose isolates runtime, migration and bootstrap database credentials.')


if __name__ == '__main__':
    main()

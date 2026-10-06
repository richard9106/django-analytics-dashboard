import copy
import os
import subprocess
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.production import validate_production_settings


# Deliberately public fixtures. They are never used in a deployed environment.
TEST_SECRET = 'ci-only-secret-key-that-is-long-enough-for-django-checks'
TEST_FERNET_KEY = 'MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA='


class ProductionConfigurationTests(SimpleTestCase):
    def setUp(self):
        self.config = {
            'DEBUG': False,
            'SECRET_KEY': TEST_SECRET,
            'ALLOWED_HOSTS': ['nuviamy.example'],
            'CSRF_TRUSTED_ORIGINS': ['https://nuviamy.example'],
            'SECURE_SSL_REDIRECT': True,
            'SESSION_COOKIE_SECURE': True,
            'CSRF_COOKIE_SECURE': True,
            'SECURE_HSTS_SECONDS': 31536000,
            'DATABASES': {'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'nuviamy_test', 'USER': 'nuviamy_test',
                'HOST': 'localhost', 'PASSWORD': 'test-only-database-password',
            }},
            'FIELD_ENCRYPTION_KEY': TEST_FERNET_KEY,
        }

    def test_secure_configuration_is_accepted(self):
        validate_production_settings(self.config)

    def test_insecure_configuration_is_rejected_without_disclosing_values(self):
        cases = [
            ('DEBUG', True), ('SECRET_KEY', ''),
            ('SECRET_KEY', 'dev-only-secret-key'),
            ('SECRET_KEY', 'sensitive-short-key'),
            ('SECRET_KEY', 'a' * 64),
            ('SECRET_KEY', 'django-insecure-' + TEST_SECRET),
            ('SECRET_KEY', 'REPLACE_WITH_A_RANDOM_SECRET_OF_AT_LEAST_50_CHARACTERS'),
            ('ALLOWED_HOSTS', []), ('ALLOWED_HOSTS', ['*']),
            ('CSRF_TRUSTED_ORIGINS', []),
            ('CSRF_TRUSTED_ORIGINS', ['http://nuviamy.example']),
            ('SECURE_SSL_REDIRECT', False), ('SESSION_COOKIE_SECURE', False),
            ('CSRF_COOKIE_SECURE', False), ('SECURE_HSTS_SECONDS', 0),
            ('FIELD_ENCRYPTION_KEY', ''),
            ('FIELD_ENCRYPTION_KEY', 'sensitive-invalid-encryption-key'),
        ]
        for name, value in cases:
            with self.subTest(setting=name, value=value):
                config = {**self.config, name: value}
                with self.assertRaises(ImproperlyConfigured) as caught:
                    validate_production_settings(config)
                self.assertNotIn(TEST_SECRET, str(caught.exception))
                self.assertNotIn(TEST_FERNET_KEY, str(caught.exception))
                if name in {'SECRET_KEY', 'FIELD_ENCRYPTION_KEY'} and value:
                    self.assertNotIn(value, str(caught.exception))

    def test_sqlite_and_incomplete_or_placeholder_database_are_rejected(self):
        database = self.config['DATABASES']['default']
        cases = [
            {**database, 'ENGINE': 'django.db.backends.sqlite3'},
            *({**database, name: ''} for name in ('NAME', 'USER', 'HOST', 'PASSWORD')),
            *({**database, 'PASSWORD': value} for value in
              ('dashboard_password', 'change-me', 'change-me-to-a-strong-password',
               'REPLACE_WITH_A_DATABASE_PASSWORD', 'password', 'postgres')),
        ]
        for value in cases:
            with self.subTest(database=value):
                config = copy.deepcopy(self.config)
                config['DATABASES']['default'] = value
                with self.assertRaises(ImproperlyConfigured):
                    validate_production_settings(config)

    def import_settings(self, overrides):
        env = {
            'PATH': os.defpath,
            'DJANGO_ENVIRONMENT': 'production',
            'DJANGO_SECRET_KEY': TEST_SECRET,
            'DJANGO_ALLOWED_HOSTS': 'nuviamy.example',
            'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://nuviamy.example',
            'POSTGRES_DB': 'nuviamy_test', 'POSTGRES_USER': 'nuviamy_test',
            'POSTGRES_PASSWORD': 'test-only-database-password',
            'POSTGRES_HOST': 'localhost',
            'FIELD_ENCRYPTION_KEY': TEST_FERNET_KEY,
        }
        env.update(overrides)
        # Prevent a developer's .env from masking missing settings in the test.
        return subprocess.run(
            [sys.executable, '-c',
             "from unittest.mock import patch\n"
             "with patch('dotenv.load_dotenv'):\n"
             " import config.settings as s\n"
             " print(s.DJANGO_ENVIRONMENT, s.DEBUG)"],
            cwd=Path(__file__).resolve().parents[2], env=env,
            capture_output=True, text=True, timeout=15,
        )

    def test_production_startup_defaults_debug_to_false(self):
        result = self.import_settings({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'production False')

    def test_production_startup_cannot_enable_debug(self):
        result = self.import_settings({'DJANGO_DEBUG': 'true'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_DEBUG must be false', result.stderr)

    def test_production_startup_cannot_use_missing_secret(self):
        result = self.import_settings({'DJANGO_SECRET_KEY': ''})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY must be', result.stderr)

    def test_legacy_debug_false_also_enforces_production_guards(self):
        result = self.import_settings({
            'DJANGO_ENVIRONMENT': '', 'DJANGO_DEBUG': 'false',
            'POSTGRES_PASSWORD': 'dashboard_password',
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('POSTGRES_PASSWORD must not be a placeholder', result.stderr)

    def test_unknown_environment_cannot_bypass_guards(self):
        result = self.import_settings({'DJANGO_ENVIRONMENT': 'prodution'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_ENVIRONMENT must be', result.stderr)

    def test_local_development_still_allows_sqlite(self):
        result = self.import_settings({
            'DJANGO_ENVIRONMENT': 'development', 'POSTGRES_DB': '',
            'DJANGO_SECRET_KEY': 'dev-only-secret-key', 'FIELD_ENCRYPTION_KEY': '',
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'development True')

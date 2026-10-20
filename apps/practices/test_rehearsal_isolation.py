from types import SimpleNamespace
from django.test import TestCase, SimpleTestCase
from django.core.management import call_command, CommandError
from unittest.mock import patch
from ops.rehearsal import validate_rehearsal, clear_restored_integrations
from .models import Practice, ExternalIntegration


class RehearsalConfigTests(SimpleTestCase):
    def config(self,**kwargs):
        return SimpleNamespace(**dict({'MIGRATION_REHEARSAL':True,'EMAIL_BACKEND':'django.core.mail.backends.dummy.EmailBackend'},**kwargs))

    def test_only_explicit_isolated_database_without_external_keys_is_accepted(self):
        validate_rehearsal(self.config(),'fictional_rehearsal',True)
        cases=[(self.config(),'production',True),(self.config(),'fictional_rehearsal',False),
            (self.config(MIGRATION_REHEARSAL=False),'fictional_rehearsal',True),
            (self.config(EMAIL_BACKEND='smtp'),'fictional_rehearsal',True),
            (self.config(STRIPE_SECRET_KEY='synthetic'),'fictional_rehearsal',True),
            (self.config(GOOGLE_OAUTH_CLIENT_ID='synthetic'),'fictional_rehearsal',True),
            (self.config(DJANGO_STORAGE_BACKEND='s3'),'fictional_rehearsal',True),
            (self.config(AWS_SESSION_TOKEN='synthetic'),'fictional_rehearsal',True)]
        for config,name,confirm in cases:
            with self.assertRaises(ValueError):validate_rehearsal(config,name,confirm)


class RestoredIntegrationTests(TestCase):
    def setUp(self):
        self.practice=Practice.objects.create(name='Fictional restored practice')
        self.integration=ExternalIntegration.objects.create(practice=self.practice,provider='google',
            status='connected',access_token='fictional-valid-access-token',refresh_token='fictional-refresh-token',
            calendar_enabled=True,send_email_enabled=True,file_storage_enabled=True)

    def test_restored_credentials_and_integration_flags_are_removed_without_network(self):
        from apps.appointments.google_calendar import get_calendar_integration
        with patch('apps.practices.google_oauth.urlopen') as network:
            self.assertEqual(clear_restored_integrations(),1)
            network.assert_not_called()
        self.integration.refresh_from_db()
        self.assertEqual(self.integration.access_token,'')
        self.assertEqual(self.integration.refresh_token,'')
        self.assertEqual(self.integration.status,'disconnected')
        self.assertFalse(self.integration.calendar_enabled)
        self.assertIsNone(get_calendar_integration(self.practice))

    def test_command_refuses_current_database_before_any_write(self):
        with self.assertRaises(CommandError):call_command('isolate_rehearsal',confirm_isolated=True)
        self.integration.refresh_from_db()
        self.assertEqual(self.integration.access_token,'fictional-valid-access-token')

    def test_restored_sessions_are_removed_before_starting_web(self):
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        from datetime import timedelta
        Session.objects.create(session_key='fictional-source-session',session_data='fictional',expire_date=timezone.now()+timedelta(days=1))
        clear_restored_integrations()
        self.assertFalse(Session.objects.exists())

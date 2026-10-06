"""Explicit teardown of disposable test data; never used by production code."""
from django.db import connection
from django.test import TransactionTestCase


class ProtectedRecordsTransactionTestCase(TransactionTestCase):
    def _fixture_teardown(self):
        if connection.vendor != 'postgresql':
            return super()._fixture_teardown()
        if not connection.settings_dict['NAME'].startswith('test_'):
            raise RuntimeError('Protected records may only be flushed in a disposable test database.')
        guards = [('audit_auditlog', 'audit_reject_truncate'),
                  ('clinical_sessionnote', 'clinical_reject_truncate')]
        with connection.cursor() as cursor:
            for table, trigger in guards:
                cursor.execute(f'ALTER TABLE {table} DISABLE TRIGGER {trigger}')
        try:
            super()._fixture_teardown()
        finally:
            with connection.cursor() as cursor:
                for table, trigger in guards:
                    cursor.execute(f'ALTER TABLE {table} ENABLE TRIGGER {trigger}')

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


ENCRYPTED_PREFIX = 'fernet:'


def get_fernet():
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
    if not key:
        raise ImproperlyConfigured('FIELD_ENCRYPTION_KEY is required to decrypt encrypted fields.')
    return Fernet(key.encode())


class EncryptedTextField(models.TextField):
    description = 'Text field encrypted at rest with Fernet'

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        if not isinstance(value, str) or not value.startswith(ENCRYPTED_PREFIX):
            return value
        token = value[len(ENCRYPTED_PREFIX):]
        try:
            return get_fernet().decrypt(token.encode()).decode()
        except InvalidToken as error:
            raise ImproperlyConfigured('Encrypted field could not be decrypted with FIELD_ENCRYPTION_KEY.') from error

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value or (isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)):
            return value
        key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
        if not key:
            return value
        encrypted = Fernet(key.encode()).encrypt(value.encode()).decode()
        return f'{ENCRYPTED_PREFIX}{encrypted}'

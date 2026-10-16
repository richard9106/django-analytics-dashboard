"""Safety checks for an isolated restored database, never production."""
def validate_rehearsal(config, database_name, confirmed):
    if not confirmed or not getattr(config,'MIGRATION_REHEARSAL',False) or not database_name.endswith('_rehearsal'):
        raise ValueError('Use a dedicated *_rehearsal database and explicit isolated confirmation.')
    if config.EMAIL_BACKEND!='django.core.mail.backends.dummy.EmailBackend':
        raise ValueError('Rehearsal requires the dummy email backend.')
    for name in ('STRIPE_SECRET_KEY','STRIPE_PUBLISHABLE_KEY','GOOGLE_OAUTH_CLIENT_ID',
                 'GOOGLE_OAUTH_CLIENT_SECRET','SENTRY_DSN','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY'):
        if getattr(config,name,''):
            raise ValueError('External credentials must be disabled before isolation.')


def clear_restored_integrations():
    from apps.practices.models import ExternalIntegration
    return ExternalIntegration.objects.update(status=ExternalIntegration.Status.DISCONNECTED,
        access_token='',refresh_token='',token_expires_at=None,oauth_state='',
        send_email_enabled=False,read_email_enabled=False,calendar_enabled=False,file_storage_enabled=False,
        enabled_scopes=[],granted_scopes=[])

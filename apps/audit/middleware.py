"""Record access decisions without URLs, search text, bodies, or clinical content."""
from uuid import UUID

from django.utils.deprecation import MiddlewareMixin
from .models import AuditLog
from .utils import log_audit_event


SENSITIVE_NAMESPACES = {'clients', 'clinical', 'documents', 'appointments', 'billing',
                        'portal', 'portal_requests', 'intake'}
SENSITIVE_VIEWS = {'dashboard', 'tasks_list', 'practice_data_export',
                   'team_management', 'team_member_action', 'profile_settings'}
SENSITIVE_ADMIN_APPS = {'clients', 'clinical', 'documents', 'appointments', 'billing',
                        'portal', 'intake', 'accounts', 'practices', 'audit'}
CONTEXT_KEYS = ('object', 'client', 'object_list', 'notes', 'session_notes',
                'treatment_plans', 'documents', 'appointments', 'invoices')


def safe_identifier(value):
    text = str(value)
    if text.isascii() and text.isdigit() and len(text) <= 20:
        return text
    try:
        return str(UUID(text))
    except (ValueError, AttributeError):
        return ''


class AccessAuditMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_authenticated:
            request._audit_actor = request.user

    def process_response(self, request, response):
        match = getattr(request, 'resolver_match', None)
        if not match:
            return response
        actor = getattr(request, '_audit_actor', None)
        namespace = match.namespace
        admin_model = getattr(getattr(match.func, 'model_admin', None), 'model', None)
        admin_sensitive = namespace == 'admin' and admin_model and admin_model._meta.app_label in SENSITIVE_ADMIN_APPS
        sensitive = namespace in SENSITIVE_NAMESPACES or match.view_name in SENSITIVE_VIEWS or admin_sensitive
        authentication = match.view_name in {'login', 'admin:login', 'password_reset'}
        reason = getattr(request, '_audit_denied_reason', '')
        denied = bool(reason or response.status_code in {401, 403, 404, 429})
        if authentication and request.method == 'POST' and response.status_code in {200, 429}:
            # No attempted username, password, or reset email is recorded.
            denied = True
            reason = 'rate_limited' if response.status_code == 429 else 'credentials_rejected'
        if not (sensitive or (authentication and denied)):
            return response
        if actor is None and not (authentication and denied):
            return response
        if not denied and not (200 <= response.status_code < 300 or (admin_sensitive and response.status_code == 302)):
            return response
        if not denied and request.method not in {'GET', 'HEAD'} and not admin_sensitive:
            return response
        identifiers = {key: safe_identifier(value) for key, value in match.kwargs.items()}
        identifiers = {key: value for key, value in identifiers.items() if value}
        metadata = {'view': match.view_name, 'method': request.method,
                    'status': response.status_code, 'targets': identifiers}
        if denied:
            metadata['reason'] = reason or 'access_rejected'
            action = AuditLog.Action.DENIED
        elif request.method in {'GET', 'HEAD'}:
            action = AuditLog.Action.VIEW
        else:
            action = AuditLog.Action.UPDATE
        if action == AuditLog.Action.VIEW:
            metadata['resources'], metadata['resources_truncated'] = self.resources(response)
        log_audit_event(request, action,
                        f'access.admin.{admin_model._meta.label}' if admin_sensitive else f'access.{namespace or match.view_name}',
                        next(iter(identifiers.values()), ''), metadata=metadata, actor=actor,
                        platform=bool(admin_sensitive or actor is None))
        return response

    @staticmethod
    def resources(response):
        context = getattr(response, 'context_data', None) or {}
        result = []
        seen = set()
        for key in CONTEXT_KEYS:
            value = context.get(key)
            if value is None:
                continue
            if hasattr(value, '_meta'):
                value = [value]
            if not hasattr(value, '__iter__') or isinstance(value, (str, dict)):
                continue
            for item in value:
                model = getattr(item, '_meta', None)
                if not model or model.app_label not in SENSITIVE_NAMESPACES:
                    continue
                identity = (model.label, str(item.pk))
                if identity in seen:
                    continue
                if len(result) == 200:
                    return result, True
                seen.add(identity)
                result.append({'model': model.label, 'id': str(item.pk)})
        return result, False

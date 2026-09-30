import json
import os
import zipfile
from io import BytesIO

from django.http import HttpResponse

from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.billing.models import Invoice, Payment, ServicePackage
from apps.clients.models import Client
from apps.clinical.models import Diagnosis, SessionNote, TreatmentPlan
from apps.dashboard.models import Task
from apps.documents.models import ClientDocument
from apps.portal.models import ClientPortalAccess


def _rows(queryset, *fields):
    return list(queryset.values(*fields))


def build_practice_export(practice, scope):
    data = {'scope': scope, 'practice': {'id': practice.pk, 'name': practice.name, 'email': practice.email}}
    if scope in {'all', 'clinical'}:
        data['clients'] = _rows(Client.objects.filter(practice=practice), 'id', 'public_id', 'first_name', 'last_name', 'email', 'phone', 'date_of_birth', 'status', 'insurance_provider', 'insurance_member_id', 'created_at', 'updated_at')
        data['appointments'] = _rows(Appointment.objects.filter(practice=practice), 'id', 'client_id', 'therapist_id', 'starts_at', 'ends_at', 'status', 'appointment_type', 'location', 'meeting_url', 'created_at')
        data['diagnoses'] = _rows(Diagnosis.objects.filter(practice=practice), 'id', 'client_id', 'code', 'label', 'diagnosed_at', 'active', 'created_at')
        data['treatment_plans'] = _rows(TreatmentPlan.objects.filter(practice=practice), 'id', 'client_id', 'therapist_id', 'title', 'status', 'goals', 'objectives', 'interventions', 'start_date', 'review_date', 'completed_at', 'created_at', 'updated_at')
        data['session_notes'] = _rows(SessionNote.objects.filter(practice=practice), 'id', 'client_id', 'therapist_id', 'appointment_id', 'treatment_plan_id', 'note_type', 'content', 'treatment_progress', 'is_locked', 'locked_at', 'created_at', 'updated_at')
        data['documents'] = _rows(ClientDocument.objects.filter(practice=practice), 'id', 'client_id', 'title', 'document_type', 'file', 'visible_to_client', 'created_at')
        data['portal_access'] = _rows(ClientPortalAccess.objects.filter(practice=practice), 'id', 'client_id', 'user_id', 'is_active', 'created_at', 'updated_at')
    if scope in {'all', 'billing'}:
        data['invoices'] = _rows(Invoice.objects.filter(practice=practice), 'id', 'client_id', 'appointment_id', 'package_id', 'invoice_number', 'amount', 'status', 'due_date', 'paid_at', 'created_at', 'updated_at')
        data['payments'] = _rows(Payment.objects.filter(practice=practice), 'id', 'client_id', 'invoice_id', 'amount', 'method', 'external_payment_id', 'paid_at', 'created_at')
        data['service_packages'] = _rows(ServicePackage.objects.filter(practice=practice), 'id', 'client_id', 'template_id', 'name', 'sessions_purchased', 'sessions_used', 'total_price', 'status', 'purchased_at', 'expires_at', 'created_at', 'updated_at')
    if scope == 'all':
        data['tasks'] = _rows(Task.objects.filter(practice=practice), 'id', 'title', 'description', 'due_date', 'priority', 'status', 'assignee_id', 'created_by_id', 'created_at', 'updated_at')
        data['audit_logs'] = _rows(AuditLog.objects.filter(practice=practice), 'id', 'actor_id', 'action', 'object_type', 'object_id', 'metadata', 'created_at')

    archive = BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('practice-data.json', json.dumps(data, default=str, indent=2))
        if scope in {'all', 'clinical'}:
            for document in ClientDocument.objects.filter(practice=practice).exclude(file=''):
                try:
                    with document.file.open('rb') as source:
                        bundle.writestr(f"documents/{document.pk}-{os.path.basename(document.file.name)}", source.read())
                except (FileNotFoundError, OSError):
                    continue
    archive.seek(0)
    response = HttpResponse(archive.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="nuviamy-{practice.pk}-export.zip"'
    return response

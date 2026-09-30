import json
import os
import zipfile
from datetime import datetime
from html import escape
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


def build_export_data(practice, scope):
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

    return data


def _download_response(content, content_type, filename):
    response = HttpResponse(content.getvalue(), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def build_zip_export(practice, scope, data):
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
    return _download_response(archive, 'application/zip', f'nuviamy-{practice.pk}-export.zip')


def _cell_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    if isinstance(value, datetime) and value.tzinfo:
        return value.replace(tzinfo=None)
    return value


def build_excel_export(practice, scope, data):
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in data.items():
        if not isinstance(rows, list):
            rows = [rows]
        sheet = workbook.create_sheet(name[:31] or 'Export')
        if not rows:
            sheet.append(['No records'])
            continue
        headers = list(rows[0].keys()) if isinstance(rows[0], dict) else ['value']
        sheet.append(headers)
        for row in rows:
            sheet.append([_cell_value(row.get(header)) if isinstance(row, dict) else _cell_value(row) for header in headers])
        sheet.freeze_panes = 'A2'
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(max(len(str(cell.value or '')) for cell in column) + 2, 42)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return _download_response(output, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', f'nuviamy-{practice.pk}-export.xlsx')


def build_pdf_export(practice, scope, data):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(letter), rightMargin=0.4 * inch, leftMargin=0.4 * inch, topMargin=0.4 * inch, bottomMargin=0.4 * inch)
    styles = getSampleStyleSheet()
    story = [Paragraph('NuviaMy Practice Data Export', styles['Title']), Paragraph(f'{practice.name} · Scope: {scope}', styles['Normal']), Spacer(1, 12)]
    for name, rows in data.items():
        story.append(Paragraph(name.replace('_', ' ').title(), styles['Heading2']))
        if isinstance(rows, dict):
            rows = [rows]
        if not rows:
            story.append(Paragraph('No records', styles['Normal']))
        else:
            headers = list(rows[0].keys()) if isinstance(rows[0], dict) else ['value']
            table_rows = [[Paragraph(str(header), styles['Heading4']) for header in headers]]
            for row in rows[:1000]:
                table_rows.append([Paragraph(escape(str(_cell_value(row.get(header) if isinstance(row, dict) else row))[:500]), styles['BodyText']) for header in headers])
            table = Table(table_rows, repeatRows=1)
            table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7052D9')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E1')), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            story.extend([table, Spacer(1, 10)])
    document.build(story)
    output.seek(0)
    return _download_response(output, 'application/pdf', f'nuviamy-{practice.pk}-export.pdf')


def build_svg_export(practice, scope, data):
    rows = [(name.replace('_', ' ').title(), len(value) if isinstance(value, list) else 1) for name, value in data.items() if name != 'practice']
    height = 150 + max(len(rows), 1) * 34
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}">', '<rect width="100%" height="100%" fill="#F8F9FB"/>', '<text x="40" y="58" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#1F2937">NuviaMy Practice Summary</text>', f'<text x="40" y="88" font-family="Arial, sans-serif" font-size="15" fill="#64748B">{escape(practice.name)} · {escape(scope)} export</text>']
    for index, (label, count) in enumerate(rows):
        y = 130 + index * 34
        parts.append(f'<text x="50" y="{y}" font-family="Arial, sans-serif" font-size="15" fill="#475569">{escape(label)}</text><text x="820" y="{y}" text-anchor="end" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="#7052D9">{count}</text>')
    parts.append('</svg>')
    return HttpResponse(''.join(parts), content_type='image/svg+xml', headers={'Content-Disposition': f'attachment; filename="nuviamy-{practice.pk}-summary.svg"'})


def build_practice_export(practice, scope, export_format='zip'):
    data = build_export_data(practice, scope)
    if export_format == 'xlsx':
        return build_excel_export(practice, scope, data)
    if export_format == 'pdf':
        return build_pdf_export(practice, scope, data)
    if export_format == 'svg':
        return build_svg_export(practice, scope, data)
    return build_zip_export(practice, scope, data)

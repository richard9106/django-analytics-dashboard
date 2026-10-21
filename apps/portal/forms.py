import json
from datetime import datetime, timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import UserProfile
from apps.appointments.models import Appointment
from .models import intake_question_label, ClientIntakeAssignment, ClientPortalAccess, ClientPortalRequest, IntakePacketTemplate, PortalConversation, PortalMessage, PublicBookingRequest


def suggest_portal_username(client):
    name_parts = [slugify(client.first_name).replace('-', '.'), slugify(client.last_name).replace('-', '.')]
    base = '.'.join(part for part in name_parts if part) or f'client.{client.pk}'
    username = base[:140]
    User = get_user_model()
    if not User.objects.filter(username__iexact=username).exists():
        return username

    suffix = 2
    while User.objects.filter(username__iexact=f'{username}.{suffix}').exists():
        suffix += 1
    return f'{username}.{suffix}'


class ClientPortalAccessForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=True)

    class Meta:
        model = ClientPortalAccess
        fields = ['client', 'is_active']

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        if practice:
            self.fields['client'].queryset = practice.clients.all()
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()

        if self.instance.pk:
            self.fields['client'].disabled = True
            self.fields['username'].initial = self.instance.user.username
            self.fields['email'].initial = self.instance.user.email
        else:
            if practice and not self.is_bound:
                client = self.fields['client'].queryset.first()
                if client:
                    self.fields['client'].initial = client
                    self.fields['username'].initial = suggest_portal_username(client)
                    self.fields['email'].initial = client.email

    def clean_client(self):
        client = self.cleaned_data['client']
        existing = ClientPortalAccess.objects.filter(client=client)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError('This client already has portal access.')
        return client

    def clean_username(self):
        username = self.cleaned_data['username']
        existing = get_user_model().objects.filter(username__iexact=username)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.user_id)
        if existing.exists():
            raise forms.ValidationError('A user with this username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        existing = get_user_model().objects.filter(email__iexact=email)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.user_id)
        if existing.exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email

    @transaction.atomic
    def save(self, commit=True):
        access = super().save(commit=False)
        access.practice = self.practice
        username = self.cleaned_data['username']
        email = self.cleaned_data['email']
        if access.pk:
            user = access.user
            user.username = username
            user.email = email
            user.save(update_fields=['username', 'email'])
        else:
            user = get_user_model().objects.create_user(username=username, email=email, password=None)
            access.user = user
        if commit:
            access.full_clean()
            access.save()
            UserProfile.objects.update_or_create(user=user, defaults={
                'practice': self.practice, 'role': UserProfile.Role.CLIENT})
            self.save_m2m()
        return access


class ClientPortalRequestForm(forms.ModelForm):
    class Meta:
        model = ClientPortalRequest
        fields = ['category', 'subject', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, portal_access=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.portal_access = portal_access
        if portal_access:
            self.instance.practice = portal_access.practice
            self.instance.client = portal_access.client
            self.instance.submitted_by = portal_access.user

    def save(self, commit=True):
        portal_request = super().save(commit=False)
        portal_request.practice = self.portal_access.practice
        portal_request.client = self.portal_access.client
        portal_request.submitted_by = self.portal_access.user
        if commit:
            portal_request.full_clean()
            portal_request.save()
            self.save_m2m()
        return portal_request


class PortalConversationForm(forms.ModelForm):
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), max_length=10000)

    class Meta:
        model = PortalConversation
        fields = ["subject"]

    def __init__(self, *args, portal_access=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.portal_access = portal_access

    @transaction.atomic
    def save(self, commit=True):
        conversation = super().save(commit=False)
        conversation.practice = self.portal_access.practice
        conversation.client = self.portal_access.client
        conversation.created_by = self.portal_access.user
        if commit:
            conversation.full_clean()
            conversation.save()
            message = PortalMessage(
                conversation=conversation,
                practice=conversation.practice,
                author=self.portal_access.user,
                author_kind=PortalMessage.AuthorKind.CLIENT,
                body=self.cleaned_data["body"],
            )
            message.full_clean()
            message.save()
        return conversation


class PortalMessageForm(forms.ModelForm):
    class Meta:
        model = PortalMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, conversation=None, author=None, author_kind=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation = conversation
        self.author = author
        self.author_kind = author_kind

    def save(self, commit=True):
        message = super().save(commit=False)
        message.conversation = self.conversation
        message.practice = self.conversation.practice
        message.author = self.author
        message.author_kind = self.author_kind
        if commit:
            message.full_clean()
            message.save()
        return message


class AppointmentChangeRequestForm(forms.ModelForm):
    class Meta:
        model = ClientPortalRequest
        fields = ['category', 'message']
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, portal_access=None, appointment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.portal_access = portal_access
        self.appointment = appointment
        self.fields['category'].choices = [
            (ClientPortalRequest.Category.RESCHEDULE, 'Reschedule — request a different appointment time'),
            (ClientPortalRequest.Category.CANCELLATION, 'Cancel — ask the practice to cancel this appointment'),
        ]
        if portal_access and appointment:
            self.instance.practice = portal_access.practice
            self.instance.client = portal_access.client
            self.instance.submitted_by = portal_access.user
            self.instance.appointment = appointment

    def clean(self):
        cleaned_data = super().clean()
        if self.appointment and self.appointment.status != Appointment.Status.SCHEDULED:
            raise forms.ValidationError('Only scheduled appointments can be changed from the portal.')
        if self.appointment and self.portal_access:
            existing = ClientPortalRequest.objects.filter(
                practice=self.portal_access.practice,
                client=self.portal_access.client,
                appointment=self.appointment,
                status__in=[ClientPortalRequest.Status.NEW, ClientPortalRequest.Status.REVIEWED],
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError(
                    'Your practice already has an open change request for this appointment.'
                )
        return cleaned_data

    def save(self, commit=True):
        portal_request = super().save(commit=False)
        portal_request.practice = self.portal_access.practice
        portal_request.client = self.portal_access.client
        portal_request.submitted_by = self.portal_access.user
        portal_request.appointment = self.appointment
        portal_request.subject = f'Appointment change request for {timezone.localtime(self.appointment.starts_at):%b %-d, %-I:%M %p}'
        if commit:
            portal_request.full_clean()
            portal_request.save()
            self.save_m2m()
        return portal_request


class PublicBookingRequestForm(forms.ModelForm):
    booking_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    requested_slot = forms.ChoiceField(
        widget=forms.RadioSelect,
        label='Available times',
        error_messages={'invalid_choice': 'Choose one of the available appointment times.'},
    )

    class Meta:
        model = PublicBookingRequest
        fields = ['first_name', 'last_name', 'email', 'phone', 'appointment_type', 'reason']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, available_slots=None, selected_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.available_slots = available_slots or []
        self.instance.practice = practice
        self.fields['booking_date'].initial = selected_date
        self.fields['requested_slot'].choices = [
            (slot['value'], slot['label'])
            for slot in self.available_slots
        ]
        self.fields['reason'].label = 'What would you like support with?'
        self.fields['reason'].required = False

    def clean_requested_slot(self):
        slot = self.cleaned_data['requested_slot']
        if slot not in {item['value'] for item in self.available_slots}:
            raise forms.ValidationError('Choose one of the available appointment times.')
        return slot

    def save(self, commit=True):
        booking_request = super().save(commit=False)
        booking_request.practice = self.practice
        selected_slot = datetime.strptime(self.cleaned_data['requested_slot'], '%Y-%m-%dT%H:%M')
        booking_request.requested_starts_at = timezone.make_aware(selected_slot)
        booking_request.requested_ends_at = booking_request.requested_starts_at + timedelta(minutes=50)
        if commit:
            booking_request.full_clean()
            booking_request.save()
            self.save_m2m()
        return booking_request


class IntakePacketTemplateForm(forms.ModelForm):
    form_structure = forms.CharField(required=False, max_length=250000, widget=forms.HiddenInput(attrs={'disabled': True}))
    question_lines = forms.CharField(
        label='Questions', required=False,
        widget=forms.Textarea(attrs={'rows': 8}),
        help_text='Enter one client-facing intake question per line.',
    )

    class Meta:
        model = IntakePacketTemplate
        fields = ['name', 'description', 'active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        if self.instance.pk and not self.is_bound:
            self.fields['question_lines'].initial = '\n'.join(self.instance.question_labels)
        from .intake_schema import pages_from_questions
        if not self.is_bound:
            self.fields['form_structure'].initial = json.dumps({'version': 1, 'pages': pages_from_questions(self.instance.questions or [])})

    def clean_name(self):
        name = self.cleaned_data['name']
        duplicates = IntakePacketTemplate.objects.filter(practice=self.practice, name=name)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError('A template with this name already exists. Choose a different name.')
        return name

    def clean_form_structure(self):
        value = self.cleaned_data.get('form_structure')
        if not value:
            return None
        from .intake_schema import flatten_schema
        try:
            return flatten_schema(json.loads(value))
        except (ValueError, TypeError, RecursionError):
            raise forms.ValidationError('The form structure is invalid. Please review the editor.')

    def clean_question_lines(self):
        if self.data.get(self.add_prefix('form_structure')):
            return self.cleaned_data.get('form_structure') or []
        questions = [line.strip() for line in self.cleaned_data['question_lines'].splitlines() if line.strip()]
        if not questions:
            raise forms.ValidationError('Add at least one intake question.')
        # Preserve legacy question metadata by label, including reordering.
        original = self.instance.questions or []
        used = set()
        matches = {}
        for index, label in enumerate(questions):
            match = next((old_index for old_index, old in enumerate(original)
                          if old_index not in used and intake_question_label(old) == label), None)
            if match is not None:
                matches[index] = match
                used.add(match)
        unmatched_new = [index for index in range(len(questions)) if index not in matches]
        unmatched_old = [index for index in range(len(original)) if index not in used]
        if len(unmatched_new) == len(unmatched_old) == 1:
            matches[unmatched_new[0]] = unmatched_old[0]
        records = []
        for index, label in enumerate(questions):
            old = original[matches[index]] if index in matches else None
            records.append({**old, 'label': label} if isinstance(old, dict) else label)
        return records

    def _post_clean(self):
        if 'question_lines' in self.cleaned_data:
            self.instance.questions = self.cleaned_data['question_lines']
        super()._post_clean()

    def _update_errors(self, errors):
        # Route model validation back to the active editor field.
        if hasattr(errors, 'error_dict') and 'questions' in errors.error_dict:
            errors.error_dict['form_structure' if self.data.get(self.add_prefix('form_structure')) else 'question_lines'] = errors.error_dict.pop('questions')
        super()._update_errors(errors)

    def save(self, commit=True):
        template = super().save(commit=False)
        template.practice = self.practice
        template.questions = self.cleaned_data['question_lines']
        if commit:
            template.full_clean()
            template.save()
            self.save_m2m()
        return template


class ClientIntakeAssignmentForm(forms.ModelForm):
    class Meta:
        model = ClientIntakeAssignment
        fields = ['client', 'template']

    def __init__(self, *args, practice=None, assigned_by=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.assigned_by = assigned_by
        if practice:
            self.fields['client'].queryset = practice.clients.all()
            self.fields['template'].queryset = practice.intake_templates.filter(active=True)
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()
            self.fields['template'].queryset = self.fields['template'].queryset.none()

    def save(self, commit=True):
        assignment = super().save(commit=False)
        assignment.practice = self.practice
        assignment.assigned_by = self.assigned_by
        assignment.status = ClientIntakeAssignment.Status.ASSIGNED
        if commit:
            assignment.full_clean()
            assignment.save()
            self.save_m2m()
        return assignment


class ClientIntakeResponseForm(forms.Form):
    def __init__(self, *args, assignment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        existing = assignment.answers if assignment else {}
        for index, question in enumerate(assignment.packet_questions):
            key = f'question_{index}'
            legacy_key = question.get('id') if isinstance(question, dict) else None
            stored = existing.get(key, existing.get(legacy_key, ''))
            authored = isinstance(question, dict) and question.get('_builder_version') == 1
            kind = question.get('type', 'long_text') if authored else 'long_text'
            kwargs = {'label': intake_question_label(question),
                      'initial': stored.get('answer', '') if isinstance(stored, dict) else stored,
                      'required': question.get('required', True) if authored else True,
                      'help_text': question.get('help_text', '') if authored else ''}
            if kind in {'single_choice', 'multiple_choice', 'dropdown', 'yes_no'}:
                options = ['Yes', 'No'] if kind == 'yes_no' else question.get('options', [])
                kwargs['choices'] = [(option, option) for option in options]
                if kind == 'multiple_choice':
                    field = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple, **kwargs)
                elif kind == 'dropdown':
                    kwargs['choices'].insert(0, ('', 'Select an option'))
                    field = forms.ChoiceField(**kwargs)
                else:
                    field = forms.ChoiceField(widget=forms.RadioSelect, **kwargs)
            else:
                field = forms.CharField(max_length=10000 if kind == 'long_text' else 500,
                    widget=forms.Textarea(attrs={'rows': 3}) if kind == 'long_text' else forms.TextInput(), **kwargs)
            self.fields[key] = field
        from .intake_schema import pages_from_questions
        self.pages = []
        for page in pages_from_questions(assignment.packet_questions):
            self.pages.append({**page, 'fields': [self[f"question_{q['index']}"] for q in page['questions']]})

    def save(self):
        answers = {}
        for index, question in enumerate(self.assignment.packet_questions):
            key = f'question_{index}'
            answers[key] = {'question': intake_question_label(question), 'answer': self.cleaned_data[key]}
        self.assignment.answers = answers
        self.assignment.status = ClientIntakeAssignment.Status.SUBMITTED
        self.assignment.submitted_at = timezone.now()
        self.assignment.save(update_fields=['answers', 'status', 'submitted_at', 'updated_at'])
        return self.assignment

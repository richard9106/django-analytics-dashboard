import secrets

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import UserProfile
from .models import ClientIntakeAssignment, ClientPortalAccess, ClientPortalRequest, IntakePacketTemplate


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


def suggest_portal_password():
    return f'Nuvia-{secrets.token_urlsafe(6)}'


class ClientPortalAccessForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=False)

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
            self.fields['password'].help_text = 'Leave blank to keep the current password.'
        else:
            self.fields['password'].required = True
            if practice and not self.is_bound:
                client = self.fields['client'].queryset.first()
                if client:
                    self.fields['client'].initial = client
                    self.fields['username'].initial = suggest_portal_username(client)
                    self.fields['email'].initial = client.email
                    self.fields['password'].initial = suggest_portal_password()

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

    @transaction.atomic
    def save(self, commit=True):
        access = super().save(commit=False)
        access.practice = self.practice
        username = self.cleaned_data['username']
        email = self.cleaned_data.get('email', '')
        password = self.cleaned_data.get('password')

        if access.pk:
            user = access.user
            user.username = username
            user.email = email
            if password:
                user.set_password(password)
            user.save()
        else:
            user = get_user_model().objects.create_user(username=username, email=email, password=password)
            access.user = user

        if commit:
            access.full_clean()
            access.save()
            profile, _created = UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'practice': self.practice,
                    'role': UserProfile.Role.CLIENT,
                },
            )
            if password:
                profile.must_change_password = True
                profile.save(update_fields=['must_change_password', 'updated_at'])
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


class IntakePacketTemplateForm(forms.ModelForm):
    question_lines = forms.CharField(
        label='Questions',
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
            self.fields['question_lines'].initial = '\n'.join(self.instance.questions)

    def clean_question_lines(self):
        questions = [line.strip() for line in self.cleaned_data['question_lines'].splitlines() if line.strip()]
        if not questions:
            raise forms.ValidationError('Add at least one intake question.')
        return questions

    def _post_clean(self):
        if 'question_lines' in self.cleaned_data:
            self.instance.questions = self.cleaned_data['question_lines']
        super()._post_clean()

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
        for index, question in enumerate(assignment.template.questions):
            key = f'question_{index}'
            self.fields[key] = forms.CharField(
                label=question,
                initial=existing.get(key, ''),
                widget=forms.Textarea(attrs={'rows': 3}),
            )

    def save(self):
        answers = {}
        for index, question in enumerate(self.assignment.template.questions):
            key = f'question_{index}'
            answers[key] = {'question': question, 'answer': self.cleaned_data[key]}
        self.assignment.answers = answers
        self.assignment.status = ClientIntakeAssignment.Status.SUBMITTED
        self.assignment.submitted_at = timezone.now()
        self.assignment.save(update_fields=['answers', 'status', 'submitted_at', 'updated_at'])
        return self.assignment

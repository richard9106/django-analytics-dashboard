from django import forms

from .models import ExternalIntegration


class ExternalIntegrationForm(forms.ModelForm):
    class Meta:
        model = ExternalIntegration
        fields = [
            'account_email',
            'send_email_enabled',
            'read_email_enabled',
            'file_storage_enabled',
            'default_folder',
            'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, practice=None, provider=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.provider = provider or getattr(self.instance, 'provider', None)
        self.instance.practice = practice
        if self.provider:
            self.instance.provider = self.provider
        if self.provider != ExternalIntegration.Provider.GMAIL:
            self.fields['send_email_enabled'].disabled = True
            self.fields['read_email_enabled'].disabled = True
        if self.provider == ExternalIntegration.Provider.GMAIL:
            self.fields['file_storage_enabled'].disabled = True

    def save(self, commit=True):
        integration = super().save(commit=False)
        integration.practice = self.practice
        integration.provider = self.provider
        integration.status = ExternalIntegration.Status.DISCONNECTED
        if integration.provider != ExternalIntegration.Provider.GMAIL:
            integration.send_email_enabled = False
            integration.read_email_enabled = False
        if integration.provider == ExternalIntegration.Provider.GMAIL:
            integration.file_storage_enabled = False
        if commit:
            integration.full_clean()
            integration.save()
            self.save_m2m()
        return integration

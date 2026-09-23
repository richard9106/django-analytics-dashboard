from django import forms

from .models import ExternalIntegration


GOOGLE_SCOPE_MAP = {
    'send_email_enabled': 'https://www.googleapis.com/auth/gmail.send',
    'read_email_enabled': 'https://www.googleapis.com/auth/gmail.readonly',
    'calendar_enabled': 'https://www.googleapis.com/auth/calendar.events',
    'file_storage_enabled': 'https://www.googleapis.com/auth/drive.file',
}


class GoogleOAuthSelectionForm(forms.ModelForm):
    class Meta:
        model = ExternalIntegration
        fields = [
            'send_email_enabled',
            'read_email_enabled',
            'calendar_enabled',
            'file_storage_enabled',
            'default_folder',
            'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.provider = ExternalIntegration.Provider.GOOGLE

    def clean(self):
        cleaned_data = super().clean()
        if not any(cleaned_data.get(field) for field in GOOGLE_SCOPE_MAP):
            raise forms.ValidationError('Select at least one Google capability before connecting.')
        return cleaned_data

    def get_enabled_scopes(self):
        return [scope for field, scope in GOOGLE_SCOPE_MAP.items() if self.cleaned_data.get(field)]


class DropboxIntegrationForm(forms.ModelForm):
    class Meta:
        model = ExternalIntegration
        fields = ['file_storage_enabled', 'default_folder', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        self.instance.provider = ExternalIntegration.Provider.DROPBOX

    def save(self, commit=True):
        integration = super().save(commit=False)
        integration.practice = self.practice
        integration.provider = ExternalIntegration.Provider.DROPBOX
        integration.send_email_enabled = False
        integration.read_email_enabled = False
        integration.calendar_enabled = False
        integration.enabled_scopes = []
        if commit:
            integration.full_clean()
            integration.save()
            self.save_m2m()
        return integration


class GmailSendForm(forms.Form):
    to_email = forms.EmailField(label='To')
    subject = forms.CharField(max_length=160)
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 6}))

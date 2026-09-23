from django import forms

from .models import ClientDocument


class ClientDocumentForm(forms.ModelForm):
    class Meta:
        model = ClientDocument
        fields = ['client', 'document_type', 'title', 'file', 'visible_to_client', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, uploaded_by=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.uploaded_by = uploaded_by
        self.instance.practice = practice
        self.instance.uploaded_by = uploaded_by
        if practice:
            self.fields['client'].queryset = practice.clients.all()
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()

    def save(self, commit=True):
        document = super().save(commit=False)
        document.practice = self.practice
        document.uploaded_by = self.uploaded_by
        uploaded_file = self.cleaned_data.get('file')
        if uploaded_file:
            document.original_filename = uploaded_file.name
            document.content_type = getattr(uploaded_file, 'content_type', '') or ''
            document.file_size = uploaded_file.size or 0
        if commit:
            document.full_clean()
            document.save()
            self.save_m2m()
        return document

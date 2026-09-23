from django import forms
from django.utils import timezone

from .models import Invoice, PackageUsage, ServicePackage, SessionPackageTemplate


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['client', 'appointment', 'package', 'invoice_number', 'amount', 'status', 'due_date', 'paid_at', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'paid_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        self.fields['invoice_number'].required = False
        self.fields['paid_at'].input_formats = ['%Y-%m-%dT%H:%M']
        if practice:
            self.fields['client'].queryset = practice.clients.all()
            self.fields['appointment'].queryset = practice.appointments.select_related('client')
            self.fields['package'].queryset = practice.service_packages.select_related('client')
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()
            self.fields['appointment'].queryset = self.fields['appointment'].queryset.none()
            self.fields['package'].queryset = self.fields['package'].queryset.none()

    def clean(self):
        cleaned_data = super().clean()
        invoice_number = cleaned_data.get('invoice_number')
        package = cleaned_data.get('package')

        if not invoice_number and not self.instance.pk:
            cleaned_data['invoice_number'] = self.build_invoice_number(package)
            self.instance.invoice_number = cleaned_data['invoice_number']

        if cleaned_data.get('status') == Invoice.Status.PAID and not cleaned_data.get('paid_at'):
            cleaned_data['paid_at'] = timezone.now()
            self.instance.paid_at = cleaned_data['paid_at']
        return cleaned_data

    def build_invoice_number(self, package):
        today = timezone.localdate()
        package_part = package.pk if package else 0
        prefix = f'PKG-{package_part}-{today:%Y%m%d}'
        sequence = (
            Invoice.objects.filter(
                practice=self.practice,
                invoice_number__startswith=prefix,
            ).count()
            + 1
        )
        return f'{prefix}-{sequence:04d}'

    def save(self, commit=True):
        invoice = super().save(commit=False)
        invoice.practice = self.practice
        if commit:
            invoice.full_clean()
            invoice.save()
            self.save_m2m()
        return invoice


class ServicePackageForm(forms.ModelForm):
    class Meta:
        model = ServicePackage
        fields = ['client', 'template', 'name', 'sessions_purchased', 'sessions_used', 'total_price', 'status', 'purchased_at', 'expires_at', 'notes']
        widgets = {
            'purchased_at': forms.DateInput(attrs={'type': 'date'}),
            'expires_at': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        if practice:
            self.fields['client'].queryset = practice.clients.all()
            self.fields['template'].queryset = practice.session_package_templates.filter(active=True)
        else:
            self.fields['client'].queryset = self.fields['client'].queryset.none()
            self.fields['template'].queryset = self.fields['template'].queryset.none()

    def save(self, commit=True):
        package = super().save(commit=False)
        package.practice = self.practice
        if commit:
            package.full_clean()
            package.save()
            self.save_m2m()
        return package


class SessionPackageTemplateForm(forms.ModelForm):
    class Meta:
        model = SessionPackageTemplate
        fields = ['name', 'sessions_included', 'price', 'description', 'active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice

    def save(self, commit=True):
        template = super().save(commit=False)
        template.practice = self.practice
        if commit:
            template.full_clean()
            template.save()
            self.save_m2m()
        return template


class PackageUsageForm(forms.ModelForm):
    class Meta:
        model = PackageUsage
        fields = ['package', 'appointment', 'quantity', 'used_at', 'notes']
        widgets = {
            'used_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.fields['used_at'].input_formats = ['%Y-%m-%dT%H:%M']
        if practice:
            self.fields['package'].queryset = practice.service_packages.select_related('client')
            self.fields['appointment'].queryset = practice.appointments.select_related('client')
        else:
            self.fields['package'].queryset = self.fields['package'].queryset.none()
            self.fields['appointment'].queryset = self.fields['appointment'].queryset.none()

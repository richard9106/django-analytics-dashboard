import re

from django import forms
from .countries import BILLING_COUNTRIES
from django.db.models import Sum
from django.utils import timezone

from .models import InsurancePayer, InsuranceRate, Invoice, PackageUsage, Payment, ServicePackage, SessionPackageTemplate


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
        self.fields['client'].required = False
        self.fields['amount'].required = False
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
        client = cleaned_data.get('client')
        appointment = cleaned_data.get('appointment')
        package = cleaned_data.get('package')
        amount = cleaned_data.get('amount')

        if not client:
            if package:
                cleaned_data['client'] = package.client
                self.instance.client = package.client
            elif appointment:
                cleaned_data['client'] = appointment.client
                self.instance.client = appointment.client

        if amount is None and package:
            cleaned_data['amount'] = package.total_price
            self.instance.amount = package.total_price
        elif amount is None:
            self.add_error('amount', 'Amount is required unless a package is selected.')

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


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['invoice', 'amount', 'method', 'external_payment_id', 'paid_at']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'paid_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        self.fields['paid_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['invoice'].queryset = (
            practice.invoices.exclude(status__in=[Invoice.Status.PAID, Invoice.Status.VOID]).select_related('client')
            if practice else Invoice.objects.none()
        )

    def clean(self):
        cleaned_data = super().clean()
        invoice = cleaned_data.get('invoice')
        amount = cleaned_data.get('amount')
        if invoice:
            self.instance.client = invoice.client
        if invoice and amount:
            paid_total = invoice.payments.aggregate(total=Sum('amount'))['total'] or 0
            remaining = invoice.amount - paid_total
            if amount > remaining:
                self.add_error('amount', f'Payment cannot exceed the invoice balance of ${remaining:.2f}.')
        return cleaned_data

    def save(self, commit=True):
        payment = super().save(commit=False)
        payment.practice = self.practice
        payment.client = payment.invoice.client
        if commit:
            payment.full_clean()
            payment.save()
        return payment


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


class InsurancePayerForm(forms.ModelForm):
    class Meta:
        model = InsurancePayer
        fields = ['name', 'payer_id', 'active', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice

    def save(self, commit=True):
        payer = super().save(commit=False)
        payer.practice = self.practice
        payer.is_system_template = False
        if commit:
            payer.full_clean()
            payer.save()
            self.save_m2m()
        return payer


class InsuranceRateForm(forms.ModelForm):
    class Meta:
        model = InsuranceRate
        fields = ['payer', 'state', 'service_code', 'service_label', 'reimbursement_amount', 'active', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, practice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.practice = practice
        self.instance.practice = practice
        payer_queryset = InsurancePayer.objects.filter(practice__isnull=True) | InsurancePayer.objects.filter(practice=practice)
        self.fields['payer'].queryset = payer_queryset.filter(active=True).order_by('name') if practice else InsurancePayer.objects.none()
        self.fields['state'].widget.attrs.update({'maxlength': 2, 'placeholder': 'CA'})

    def clean_state(self):
        return self.cleaned_data['state'].upper()

    def save(self, commit=True):
        rate = super().save(commit=False)
        rate.practice = self.practice
        if commit:
            rate.full_clean()
            rate.save()
            self.save_m2m()
        return rate


class PackageUsageForm(forms.ModelForm):
    class Meta:
        model = PackageUsage
        fields = ['package', 'appointment', 'quantity', 'charge_reason', 'used_at', 'notes']
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


class ProfessionalBillingForm(forms.Form):
    legal_name = forms.CharField(label='Legal billing name', max_length=200, help_text='Your business or professional name as it should appear on invoices.')
    line1 = forms.CharField(label='Address line 1', max_length=200)
    line2 = forms.CharField(label='Address line 2', max_length=200, required=False)
    city = forms.CharField(max_length=100)
    US_STATES = [('', 'Select state')] + [(code, name) for code, name in [
        ('AL','Alabama'),('AK','Alaska'),('AZ','Arizona'),('AR','Arkansas'),('CA','California'),('CO','Colorado'),('CT','Connecticut'),('DE','Delaware'),('DC','District of Columbia'),('FL','Florida'),('GA','Georgia'),('HI','Hawaii'),('ID','Idaho'),('IL','Illinois'),('IN','Indiana'),('IA','Iowa'),('KS','Kansas'),('KY','Kentucky'),('LA','Louisiana'),('ME','Maine'),('MD','Maryland'),('MA','Massachusetts'),('MI','Michigan'),('MN','Minnesota'),('MS','Mississippi'),('MO','Missouri'),('MT','Montana'),('NE','Nebraska'),('NV','Nevada'),('NH','New Hampshire'),('NJ','New Jersey'),('NM','New Mexico'),('NY','New York'),('NC','North Carolina'),('ND','North Dakota'),('OH','Ohio'),('OK','Oklahoma'),('OR','Oregon'),('PA','Pennsylvania'),('RI','Rhode Island'),('SC','South Carolina'),('SD','South Dakota'),('TN','Tennessee'),('TX','Texas'),('UT','Utah'),('VT','Vermont'),('VA','Virginia'),('WA','Washington'),('WV','West Virginia'),('WI','Wisconsin'),('WY','Wyoming')]]
    country = forms.ChoiceField(label='Country', choices=BILLING_COUNTRIES, initial='US')
    state = forms.CharField(label='State, province or region', max_length=100, required=False)
    postal_code = forms.CharField(label='Postal code', max_length=20, required=False)
    professional_purchase = forms.BooleanField(label='I am purchasing NuviaMy for my business or professional practice and am authorized to make this purchase.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        autocomplete = {'legal_name':'organization','line1':'address-line1','line2':'address-line2','city':'address-level2','state':'address-level1','postal_code':'postal-code'}
        for name, field in self.fields.items():
            field.widget.attrs['aria-describedby'] = f'{name}-help {name}-errors'
            if name in autocomplete:
                field.widget.attrs['autocomplete'] = autocomplete[name]
        self.order_fields(['legal_name','country','line1','line2','city','state','postal_code','professional_purchase'])
        country = self.data.get('country') if self.is_bound else self.initial.get('country', 'US')
        if country == 'US':
            self.fields['state'].required = True
            self.fields['state'].label = 'State'
            self.fields['state'].help_text = 'Enter the state name or its two-letter abbreviation.'
            self.fields['postal_code'].required = True
            self.fields['postal_code'].label = 'ZIP code'
        else:
            self.fields['state'].help_text = 'Optional where your billing address does not use a region.'
            self.fields['postal_code'].help_text = 'Optional where your billing address does not use a postal code.'

    def clean(self):
        data = super().clean()
        if data.get('country') == 'US':
            state = data.get('state', '')
            states = dict(self.US_STATES)
            code = next((code for code, name in states.items() if name.lower() == state.lower()), state.upper())
            if state and code not in states:
                self.add_error('state', 'Enter a valid United States state or District of Columbia.')
            else:
                data['state'] = code
            postal = data.get('postal_code', '')
            if postal and not re.fullmatch(r'\d{5}(-\d{4})?', postal):
                self.add_error('postal_code', 'Enter a five-digit ZIP code or ZIP+4.')
        return data

    def stripe_address(self):
        return {key:self.cleaned_data[key] for key in ('line1','line2','city','state','postal_code','country')}

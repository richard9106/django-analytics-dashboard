from django.urls import path

from .views import (
    BillingListView,
    InsurancePayerCreateView,
    InsurancePayerDeleteView,
    InsurancePayerUpdateView,
    InsuranceRateCreateView,
    InsuranceRateDeleteView,
    InsuranceRateUpdateView,
    InsuranceSettingsView,
    InvoiceCreateView,
    InvoiceDeleteView,
    InvoicePrintableView,
    InvoiceSuperbillView,
    InvoiceUpdateView,
    PackageCreateView,
    PackageDeleteView,
    PackageUpdateView,
    PackageUsageCreateView,
    PackageUsageDeleteView,
    SessionPackageTemplateCreateView,
    SessionPackageTemplateDeleteView,
    SessionPackageTemplateListView,
    SessionPackageTemplateUpdateView,
)

app_name = 'billing'

urlpatterns = [
    path('', BillingListView.as_view(), name='list'),
    path('invoices/new/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/edit/', InvoiceUpdateView.as_view(), name='invoice_edit'),
    path('invoices/<int:pk>/print/', InvoicePrintableView.as_view(), name='invoice_print'),
    path('invoices/<int:pk>/superbill/', InvoiceSuperbillView.as_view(), name='invoice_superbill'),
    path('invoices/<int:pk>/delete/', InvoiceDeleteView.as_view(), name='invoice_delete'),
    path('packages/new/', PackageCreateView.as_view(), name='package_create'),
    path('packages/<int:pk>/edit/', PackageUpdateView.as_view(), name='package_edit'),
    path('packages/<int:pk>/delete/', PackageDeleteView.as_view(), name='package_delete'),
    path('usage/new/', PackageUsageCreateView.as_view(), name='usage_create'),
    path('usage/<int:pk>/delete/', PackageUsageDeleteView.as_view(), name='usage_delete'),
]

settings_patterns = [
    path('session-packages/', SessionPackageTemplateListView.as_view(), name='package_templates'),
    path('session-packages/new/', SessionPackageTemplateCreateView.as_view(), name='package_template_create'),
    path('session-packages/<int:pk>/edit/', SessionPackageTemplateUpdateView.as_view(), name='package_template_edit'),
    path('session-packages/<int:pk>/delete/', SessionPackageTemplateDeleteView.as_view(), name='package_template_delete'),
    path('insurance/', InsuranceSettingsView.as_view(), name='insurance'),
    path('insurance/payers/new/', InsurancePayerCreateView.as_view(), name='insurance_payer_create'),
    path('insurance/payers/<int:pk>/edit/', InsurancePayerUpdateView.as_view(), name='insurance_payer_edit'),
    path('insurance/payers/<int:pk>/delete/', InsurancePayerDeleteView.as_view(), name='insurance_payer_delete'),
    path('insurance/rates/new/', InsuranceRateCreateView.as_view(), name='insurance_rate_create'),
    path('insurance/rates/<int:pk>/edit/', InsuranceRateUpdateView.as_view(), name='insurance_rate_edit'),
    path('insurance/rates/<int:pk>/delete/', InsuranceRateDeleteView.as_view(), name='insurance_rate_delete'),
]

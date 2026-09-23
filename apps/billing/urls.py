from django.urls import path

from .views import (
    BillingListView,
    InvoiceCreateView,
    InvoiceDeleteView,
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
]

from django.urls import path

from .views import AppointmentChangeRequestCreateView, ClientInvoicePaymentView, ClientIntakeCompleteView, ClientPortalDashboardView, ClientPortalRequestCreateView

app_name = 'portal'

urlpatterns = [
    path('', ClientPortalDashboardView.as_view(), name='dashboard'),
    path('invoices/<int:pk>/pay/', ClientInvoicePaymentView.as_view(), name='invoice_pay'),
    path('intake/<int:pk>/', ClientIntakeCompleteView.as_view(), name='intake_complete'),
    path('appointments/<int:pk>/change-request/', AppointmentChangeRequestCreateView.as_view(), name='appointment_change_request'),
    path('requests/new/', ClientPortalRequestCreateView.as_view(), name='request_create'),
]

from django.urls import path

from .views import AppointmentCreateView, AppointmentDeleteView, AppointmentGoogleSyncView, AppointmentListView, AppointmentUpdateView

app_name = 'appointments'

urlpatterns = [
    path('', AppointmentListView.as_view(), name='list'),
    path('new/', AppointmentCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', AppointmentUpdateView.as_view(), name='edit'),
    path('<int:pk>/sync/google/', AppointmentGoogleSyncView.as_view(), name='google_sync'),
    path('<int:pk>/delete/', AppointmentDeleteView.as_view(), name='delete'),
]

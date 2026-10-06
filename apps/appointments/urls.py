from django.urls import path
from .views import CalendarAvailabilityUpdateView, AppointmentCancelView

from .views import AppointmentCreateView, AppointmentDeleteView, AppointmentGoogleSyncView, AppointmentListView, AppointmentRescheduleView, AppointmentSeriesCancelView, AppointmentSeriesUpdateView, AppointmentUpdateView, CalendarAvailabilityCreateView, CalendarAvailabilityDeleteView, CalendarSyncIssuesView

app_name = 'appointments'

urlpatterns = [
    path('', AppointmentListView.as_view(), name='list'),
    path('sync-issues/', CalendarSyncIssuesView.as_view(), name='sync_issues'),
    path('availability/', CalendarAvailabilityCreateView.as_view(), name='availability_create'),
    path('availability/<int:pk>/edit/', CalendarAvailabilityUpdateView.as_view(), name='availability_edit'),
    path('availability/<int:pk>/delete/', CalendarAvailabilityDeleteView.as_view(), name='availability_delete'),
    path('new/', AppointmentCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', AppointmentUpdateView.as_view(), name='edit'),
    path('<int:pk>/cancel/', AppointmentCancelView.as_view(), name='cancel'),
    path('<int:pk>/reschedule/', AppointmentRescheduleView.as_view(), name='reschedule'),
    path('<int:pk>/sync/google/', AppointmentGoogleSyncView.as_view(), name='google_sync'),
    path('<int:pk>/series/update/', AppointmentSeriesUpdateView.as_view(), name='series_update'),
    path('<int:pk>/series/cancel/', AppointmentSeriesCancelView.as_view(), name='series_cancel'),
    path('<int:pk>/delete/', AppointmentDeleteView.as_view(), name='delete'),
]

from django.urls import path

from .views import AppointmentCreateView, AppointmentDeleteView, AppointmentListView, AppointmentUpdateView

app_name = 'appointments'

urlpatterns = [
    path('', AppointmentListView.as_view(), name='list'),
    path('new/', AppointmentCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', AppointmentUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', AppointmentDeleteView.as_view(), name='delete'),
]

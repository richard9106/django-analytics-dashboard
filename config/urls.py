from django.contrib import admin
from django.urls import path

from apps.dashboard.views import DashboardView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', DashboardView.as_view(), name='dashboard'),
]

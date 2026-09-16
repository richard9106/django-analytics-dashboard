from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from apps.dashboard.views import DashboardView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', LoginView.as_view(template_name='dashboard/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', DashboardView.as_view(), name='dashboard'),
]

from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.dashboard.views import DashboardView
from apps.billing.urls import settings_patterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('appointments/', include('apps.appointments.urls')),
    path('clients/', include('apps.clients.urls')),
    path('clinical-notes/', include('apps.clinical.urls')),
    path('billing/', include('apps.billing.urls')),
    path('settings/', include((settings_patterns, 'settings'), namespace='settings')),
    path('login/', LoginView.as_view(template_name='dashboard/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('summernote/', include('django_summernote.urls')),
    path('', DashboardView.as_view(), name='dashboard'),
] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, 
                          document_root=settings.MEDIA_ROOT)

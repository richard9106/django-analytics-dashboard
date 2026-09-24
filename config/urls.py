from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path, include
from django.views.generic import RedirectView, TemplateView
from django.conf import settings
from django.conf.urls.static import static

from apps.dashboard.views import DashboardView, HomePageView
from apps.billing.urls import settings_patterns
from apps.accounts.views import ForcePasswordChangeView, RoleAwareLoginView
from apps.portal.settings_urls import urlpatterns as portal_settings_patterns
from apps.portal.intake_urls import urlpatterns as intake_patterns
from apps.portal.practice_urls import urlpatterns as portal_request_patterns
from apps.practices.settings_urls import urlpatterns as practice_settings_patterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('appointments/', include('apps.appointments.urls')),
    path('clients/', include('apps.clients.urls')),
    path('clinical-notes/', include('apps.clinical.urls')),
    path('billing/', include('apps.billing.urls')),
    path('settings/', include((settings_patterns, 'settings'), namespace='settings')),
    path('settings/', include((portal_settings_patterns, 'portal_settings'), namespace='portal_settings')),
    path('settings/', include((practice_settings_patterns, 'practice_settings'), namespace='practice_settings')),
    path('documents/', include('apps.documents.urls')),
    path('intake/', include((intake_patterns, 'intake'), namespace='intake')),
    path('requests/', include((portal_request_patterns, 'portal_requests'), namespace='portal_requests')),
    path('portal/', include('apps.portal.urls')),
    path('login/', RoleAwareLoginView.as_view(), name='login'),
    path('change-temporary-password/', ForcePasswordChangeView.as_view(), name='force_password_change'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('summernote/', include('django_summernote.urls')),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('robots.txt', TemplateView.as_view(template_name='marketing/robots.txt', content_type='text/plain'), name='robots_txt'),
    path('sitemap.xml', TemplateView.as_view(template_name='marketing/sitemap.xml', content_type='application/xml'), name='sitemap_xml'),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.svg', permanent=True), name='favicon'),
    path('', HomePageView.as_view(), name='home'),
] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, 
                          document_root=settings.MEDIA_ROOT)

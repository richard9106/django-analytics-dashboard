from django.contrib import admin
from django.contrib.auth.views import LogoutView, PasswordResetCompleteView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView
from django.urls import path, include
from django.views.generic import RedirectView, TemplateView
from django.conf import settings
from django.conf.urls.static import static

from apps.dashboard.views import (
    ClinicalNotesSoftwarePageView,
    ClientPortalSoftwarePageView,
    DashboardView,
    StaffMonitoringView,
    TaskCreateView,
    TaskListView,
    TaskStatusUpdateView,
    FeaturesPageView,
    HomePageView,
    HelpCenterView,
    SupportContactView,
    MentalHealthBillingSoftwarePageView,
    PricingPageView,
    TherapyPracticeManagementPageView,
    TherapySchedulingPageView,
)
from apps.billing.urls import settings_patterns
from apps.accounts.views import ForcePasswordChangeView, RoleAwareLoginView
from apps.portal.settings_urls import urlpatterns as portal_settings_patterns
from apps.portal.intake_urls import urlpatterns as intake_patterns
from apps.portal.practice_urls import urlpatterns as portal_request_patterns
from apps.portal.views import PublicBookingRequestCreateView
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
    path('book/<slug:slug>/', PublicBookingRequestCreateView.as_view(), name='public_booking'),
    path('login/', RoleAwareLoginView.as_view(), name='login'),
    path('password-reset/', PasswordResetView.as_view(template_name='registration/password_reset_form.html', email_template_name='registration/password_reset_email.html', subject_template_name='registration/password_reset_subject.txt', success_url='/password-reset/done/'), name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html', success_url='/password-reset/complete/'), name='password_reset_confirm'),
    path('password-reset/complete/', PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    path('change-temporary-password/', ForcePasswordChangeView.as_view(), name='force_password_change'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('summernote/', include('django_summernote.urls')),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('staff/monitoring/', StaffMonitoringView.as_view(), name='staff_monitoring'),
    path('tasks/', TaskListView.as_view(), name='tasks_list'),
    path('tasks/create/', TaskCreateView.as_view(), name='tasks_create'),
    path('tasks/<int:pk>/status/', TaskStatusUpdateView.as_view(), name='tasks_status'),
    path('features/', FeaturesPageView.as_view(), name='features'),
    path('pricing/', PricingPageView.as_view(), name='pricing'),
    path('help/', HelpCenterView.as_view(), name='help_center'),
    path('help/contact/', SupportContactView.as_view(), name='support_contact'),
    path('cookie-policy/', TemplateView.as_view(template_name='marketing/cookie_policy.html'), name='cookie_policy'),
    path('therapy-practice-management-software/', TherapyPracticeManagementPageView.as_view(), name='therapy_practice_management'),
    path('therapy-scheduling-software/', TherapySchedulingPageView.as_view(), name='therapy_scheduling_software'),
    path('clinical-notes-software-for-therapists/', ClinicalNotesSoftwarePageView.as_view(), name='clinical_notes_software'),
    path('client-portal-software-for-therapists/', ClientPortalSoftwarePageView.as_view(), name='client_portal_software'),
    path('mental-health-billing-software/', MentalHealthBillingSoftwarePageView.as_view(), name='mental_health_billing_software'),
    path('robots.txt', TemplateView.as_view(template_name='marketing/robots.txt', content_type='text/plain'), name='robots_txt'),
    path('sitemap.xml', TemplateView.as_view(template_name='marketing/sitemap.xml', content_type='application/xml'), name='sitemap_xml'),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.svg', permanent=True), name='favicon'),
    path('', HomePageView.as_view(), name='home'),
] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, 
                          document_root=settings.MEDIA_ROOT)

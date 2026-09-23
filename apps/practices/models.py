from django.core.exceptions import ValidationError
from django.db import models


class Practice(models.Model):
    class PracticeType(models.TextChoices):
        SOLO = 'solo', 'Solo Practice'
        CLINIC = 'clinic', 'Clinic / Group Practice'
    name = models.CharField(max_length=140)
    practice_type = models.CharField(max_length=60, 
                                     default=PracticeType.SOLO,
                                     choices=PracticeType.choices)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address_line1 = models.CharField(max_length=140, blank=True)
    address_line2 = models.CharField(max_length=140, blank=True)
    city = models.CharField(max_length=60, blank=True)
    state = models.CharField(max_length=60, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return str(self.name + ' - ' + self.get_practice_type_display())
    

class TherapistProfile(models.Model):
    user = models.OneToOneField('auth.User',
                                on_delete=models.CASCADE, 
                                related_name='therapist_profile')
    practice = models.ForeignKey(Practice,
                                 on_delete=models.CASCADE, 
                                 related_name='therapists')
    license_number = models.CharField(max_length=60)
    license_state = models.CharField(max_length=60)
    specialty = models.CharField(max_length=140, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['license_number', 'license_state'],
                name='unique_license_per_state')
        ]

    def __str__(self):
        display_name = self.user.get_full_name() or self.user.username
        return f"{display_name} - {self.practice.name}"


class ExternalIntegration(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        DROPBOX = "dropbox", "Dropbox"

    class Status(models.TextChoices):
        DISCONNECTED = "disconnected", "Disconnected"
        CONNECTED = "connected", "Connected"
        NEEDS_REAUTH = "needs_reauth", "Needs reauthorization"

    practice = models.ForeignKey(Practice, on_delete=models.CASCADE, related_name="external_integrations")
    provider = models.CharField(max_length=30, choices=Provider.choices)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DISCONNECTED)
    account_email = models.EmailField(blank=True)
    enabled_scopes = models.JSONField(default=list, blank=True)
    granted_scopes = models.JSONField(default=list, blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    oauth_state = models.CharField(max_length=120, blank=True)
    send_email_enabled = models.BooleanField(default=False)
    read_email_enabled = models.BooleanField(default=False)
    calendar_enabled = models.BooleanField(default=False)
    file_storage_enabled = models.BooleanField(default=False)
    default_folder = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider"]
        constraints = [
            models.UniqueConstraint(fields=["practice", "provider"], name="unique_external_integration_per_practice_provider"),
        ]

    def clean(self):
        errors = {}
        if self.provider != self.Provider.GOOGLE and (self.send_email_enabled or self.read_email_enabled or self.calendar_enabled):
            errors["provider"] = "Only Google can be used for Gmail or Calendar features."
        if errors:
            raise ValidationError(errors)

    def disconnect(self):
        self.status = self.Status.DISCONNECTED
        self.account_email = ""
        self.enabled_scopes = []
        self.granted_scopes = []
        self.access_token = ""
        self.refresh_token = ""
        self.token_expires_at = None
        self.oauth_state = ""
        self.connected_at = None

    def __str__(self):
        return f"{self.practice.name} - {self.get_provider_display()}"

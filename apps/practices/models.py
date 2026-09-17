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
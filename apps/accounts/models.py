from django.core.exceptions import ValidationError
from django.db import models


class UserProfile(models.Model):
    """Application role and practice membership for a Django user."""

    class Role(models.TextChoices):
        OWNER = "owner", "Practice Owner"
        THERAPIST = "therapist", "Therapist"
        ADMIN = "admin", "Practice Admin"
        CLIENT = "client", "Client"

    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="nuvia_profile",
    )
    practice = models.ForeignKey(
        "practices.Practice",
        on_delete=models.CASCADE,
        related_name="user_profiles",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=20, blank=True)
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def clean(self):
        errors = {}
        if self.role == self.Role.THERAPIST:
            therapist_profile = getattr(self.user, "therapist_profile", None)
            if therapist_profile and therapist_profile.practice_id != self.practice_id:
                errors["practice"] = "Therapist user profile must belong to the same practice as the therapist profile."
        if self.role not in {self.Role.CLIENT, self.Role.OWNER} and self.practice_id:
            subscription = getattr(self.practice, "subscription", None)
            if subscription and not subscription.can_add_internal_user(exclude_profile_id=self.pk):
                errors["role"] = (
                    f"Your {subscription.get_plan_display()} plan allows up to "
                    f"{subscription.internal_user_limit} team seat(s), plus the owner. Upgrade to add more team members."
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.user} - {self.get_role_display()}"

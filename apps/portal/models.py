from django.core.exceptions import ValidationError
from django.db import models


class ClientPortalAccess(models.Model):
    """Links a Django user to a client record for portal access."""

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="client_portal_access")
    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="portal_accesses")
    client = models.OneToOneField("clients.Client", on_delete=models.CASCADE, related_name="portal_access")
    is_active = models.BooleanField(default=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.client_id and self.practice_id and self.client.practice_id != self.practice_id:
            raise ValidationError({"client": "Portal client must belong to the same practice."})

    def __str__(self):
        return f"Portal access for {self.client}"

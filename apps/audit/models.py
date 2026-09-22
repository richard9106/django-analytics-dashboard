from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        VIEW = "view", "View"
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        EXPORT = "export", "Export"

    practice = models.ForeignKey("practices.Practice", on_delete=models.CASCADE, related_name="audit_logs")
    actor = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=20, choices=Action.choices)
    object_type = models.CharField(max_length=120)
    object_id = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} {self.object_type}"

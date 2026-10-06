from django.core.exceptions import ValidationError
from django.db import models


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Audit events cannot be changed.')

    def delete(self):
        raise ValidationError('Audit events cannot be deleted.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('Audit events cannot be changed.')

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False,
                    update_fields=None, unique_fields=None):
        if update_conflicts:
            raise ValidationError('Audit events cannot be changed.')
        objs = list(objs)
        for obj in objs:
            obj.capture_actor()
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts,
                                   update_conflicts=update_conflicts, update_fields=update_fields,
                                   unique_fields=unique_fields)


class AuditLog(models.Model):
    class Action(models.TextChoices):
        VIEW = 'view', 'View'
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        EXPORT = 'export', 'Export'
        DENIED = 'denied', 'Access denied'

    practice = models.ForeignKey('practices.Practice', on_delete=models.PROTECT,
                                 null=True, blank=True, related_name='audit_logs')
    actor = models.ForeignKey('auth.User', on_delete=models.PROTECT,
                              null=True, blank=True, related_name='audit_logs')
    actor_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    actor_username_snapshot = models.CharField(max_length=150, blank=True, default='', db_default='')
    action = models.CharField(max_length=20, choices=Action.choices)
    object_type = models.CharField(max_length=120)
    object_id = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['practice', 'created_at'], name='audit_practice_time_idx'),
                   models.Index(fields=['actor_id_snapshot', 'created_at'], name='audit_actor_time_idx')]

    def capture_actor(self):
        if self.actor_id:
            self.actor_id_snapshot = self.actor_id
            self.actor_username_snapshot = self.actor.username

    def save(self, *args, **kwargs):
        if not self._state.adding or (self.pk and type(self).objects.filter(pk=self.pk).exists()):
            raise ValidationError('Audit events cannot be changed.')
        self.capture_actor()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Audit events cannot be deleted.')

    def __str__(self):
        return f'{self.get_action_display()} {self.object_type}'

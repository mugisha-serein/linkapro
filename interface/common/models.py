from django.conf import settings
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def delete(self, user=None):
        return self.update(is_deleted=True, deleted_at=timezone.now(), deleted_by=user)

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted(self):
        return self.with_deleted().deleted()


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_deleted",
    )

    objects = SoftDeleteManager()
    all_objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None, user_id=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user_id is not None:
            self.deleted_by_id = user_id
        else:
            self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])

    def restore(self, user=None):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])

    def delete(self, using=None, keep_parents=False, hard=False, user=None, user_id=None):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.soft_delete(user=user, user_id=user_id)

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

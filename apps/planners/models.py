from django.db import models
from django.conf import settings

# Create your models here.

class PlannerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='planner_profile')
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    # optional preferences - can add specific fields or JSONField
    preferences = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Planner Profile for {self.user.email}"

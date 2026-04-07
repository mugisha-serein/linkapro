from django.db import models
from django.conf import settings

# Create your models here.

class AdminProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_profile')
    # Add admin-specific fields here
    # For example:
    # department = models.CharField(max_length=255, blank=True)
    # etc.

    def __str__(self):
        return f"Admin Profile for {self.user.email}"

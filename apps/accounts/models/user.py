from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError

import uuid

from .managers import UserManager

class User(AbstractBaseUser, PermissionsMixin):
    class Roles(models.TextChoices):
        PLANNER = 'planner', 'Planner'
        VENDOR = 'vendor', 'Vendor'
        ADMIN = 'admin', 'Admin'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, blank=False, null=False)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.PLANNER)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        # Role protection: immutable after creation
        if not self._state.adding:  # Only check for existing users
            original = User.objects.get(pk=self.pk)
            if original.role != self.role:
                raise ValueError("User role cannot be changed after creation")
        super().save(*args, **kwargs)

    def clean(self):
        # One Profile Rule validation
        if self.role == self.Roles.PLANNER and not hasattr(self, 'planner_profile'):
            raise ValidationError("Planner users must have a PlannerProfile")
        elif self.role == self.Roles.VENDOR and not hasattr(self, 'vendor_profile'):
            raise ValidationError("Vendor users must have a VendorProfile")
        elif self.role == self.Roles.ADMIN and not hasattr(self, 'admin_profile'):
            raise ValidationError("Admin users must have an AdminProfile")

    @property
    def profile(self):
        if self.role == self.Roles.PLANNER:
            return self.planner_profile
        elif self.role == self.Roles.VENDOR:
            return self.vendor_profile
        elif self.role == self.Roles.ADMIN:
            return self.admin_profile
        return None
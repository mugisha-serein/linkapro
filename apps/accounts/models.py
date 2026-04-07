from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import transaction

import uuid

# Create your models here.

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

    @transaction.atomic
    def create_planner(self, email, password, **extra_fields):
        extra_fields.setdefault('role', User.Roles.PLANNER)
        extra_fields.setdefault('is_verified', False)
        user = self.create_user(email, password, **extra_fields)
        # Create PlannerProfile
        from planners.models import PlannerProfile
        PlannerProfile.objects.create(user=user)
        return user

    @transaction.atomic
    def create_vendor(self, email, password, business_name='', phone='', location='', **extra_fields):
        extra_fields.setdefault('role', User.Roles.VENDOR)
        user = self.create_user(email, password, **extra_fields)
        # Create VendorProfile with DRAFT status
        from vendors.models import VendorProfile
        VendorProfile.objects.create(
            user=user,
            business_name=business_name,
            phone=phone,
            location=location,
            approval_status=VendorProfile.ApprovalStatus.DRAFT
        )
        return user

    @transaction.atomic
    def create_admin(self, email, password, **extra_fields):
        extra_fields.setdefault('role', User.Roles.ADMIN)
        extra_fields.setdefault('is_staff', True)
        user = self.create_user(email, password, **extra_fields)
        # Create AdminProfile
        from admin_panel.models import AdminProfile
        AdminProfile.objects.create(user=user)
        return user

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
        if self.pk:
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

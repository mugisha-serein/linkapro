from django.db import models
from django.contrib.auth.models import BaseUserManager
from django.db import transaction

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
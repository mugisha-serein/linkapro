from django.db import transaction

from ..models import User


@transaction.atomic
def register_planner(email, password, full_name='', **extra_fields):
    extra_fields.setdefault('role', User.Roles.PLANNER)
    extra_fields.setdefault('is_verified', False)

    user = User.objects.create_user(email=email, password=password, **extra_fields)

    from planners.models import PlannerProfile

    PlannerProfile.objects.create(user=user, full_name=full_name)
    return user


@transaction.atomic
def register_vendor(email, password, business_name='', phone='', location='', **extra_fields):
    extra_fields.setdefault('role', User.Roles.VENDOR)
    extra_fields.setdefault('is_verified', False)

    user = User.objects.create_user(email=email, password=password, **extra_fields)

    from vendors.models import VendorProfile

    VendorProfile.objects.create(
        user=user,
        business_name=business_name,
        phone=phone,
        location=location,
        approval_status=VendorProfile.ApprovalStatus.DRAFT,
    )
    return user


@transaction.atomic
def create_admin_user(email, password, **extra_fields):
    extra_fields.setdefault('role', User.Roles.ADMIN)
    extra_fields.setdefault('is_staff', True)
    extra_fields.setdefault('is_superuser', True)

    user = User.objects.create_user(email=email, password=password, **extra_fields)

    from admin_panel.models import AdminProfile

    AdminProfile.objects.create(user=user)
    return user

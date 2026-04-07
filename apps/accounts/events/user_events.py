from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import User

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Profile creation is handled in UserManager, but as backup
        if instance.role == User.Roles.PLANNER and not hasattr(instance, 'planner_profile'):
            from planners.models import PlannerProfile
            PlannerProfile.objects.create(user=instance)
        elif instance.role == User.Roles.VENDOR and not hasattr(instance, 'vendor_profile'):
            from vendors.models import VendorProfile
            VendorProfile.objects.create(user=instance, approval_status=VendorProfile.ApprovalStatus.DRAFT)
        elif instance.role == User.Roles.ADMIN and not hasattr(instance, 'admin_profile'):
            from admin_panel.models import AdminProfile
            AdminProfile.objects.create(user=instance)
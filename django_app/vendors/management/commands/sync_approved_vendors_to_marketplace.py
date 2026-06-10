from django.core.management.base import BaseCommand

from django_app.vendors.models import VendorProfile
from tasks.marketplace_sync import sync_vendor_listing_to_fastapi


class Command(BaseCommand):
    help = "Sync only admin-approved vendor profiles to the marketplace projection."

    def handle(self, *args, **options):
        approved_vendors = VendorProfile.objects.filter(status=VendorProfile.Status.APPROVED)
        synced = 0

        for vendor in approved_vendors.iterator():
            sync_vendor_listing_to_fastapi(
                str(vendor.id),
                vendor.business_name,
                vendor.category,
                vendor.description,
                vendor.service_area,
                None,
                vendor.status,
            )
            synced += 1

        self.stdout.write(self.style.SUCCESS(f"Synced {synced} approved vendor marketplace listing(s)."))

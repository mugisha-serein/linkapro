from django.core.management.base import BaseCommand

from django_app.vendors.models import VendorProfile
from tasks.marketplace_sync import sync_vendor_listing_to_fastapi


class Command(BaseCommand):
    help = "Sync only admin-approved vendor profiles to the marketplace projection."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List approved vendors without syncing them.")

    def handle(self, *args, **options):
        approved_vendors = VendorProfile.objects.filter(status=VendorProfile.Status.APPROVED)
        synced = 0
        failed = 0

        for vendor in approved_vendors.iterator():
            if options["dry_run"]:
                self.stdout.write(f"Would sync approved vendor {vendor.id} ({vendor.business_name})")
                continue
            try:
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
                self.stdout.write(f"Synced approved vendor {vendor.id} ({vendor.business_name})")
            except Exception as exc:
                failed += 1
                self.stderr.write(f"Failed to sync vendor {vendor.id} ({vendor.business_name}): {exc}")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Dry run complete for {approved_vendors.count()} approved vendor(s)."))
            return

        self.stdout.write(self.style.SUCCESS(f"Synced {synced} approved vendor marketplace listing(s); {failed} failed."))

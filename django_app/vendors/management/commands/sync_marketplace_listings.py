from django.core.management.base import BaseCommand, CommandError

from django_app.vendors.models import VendorProfile
from infrastructure.adapters.marketplace_projection import sync_vendor_to_marketplace


class Command(BaseCommand):
    help = "Sync approved vendor profiles to the FastAPI marketplace projection."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List approved vendors without syncing them.")

    def handle(self, *args, **options):
        approved_vendors = VendorProfile.objects.filter(status=VendorProfile.Status.APPROVED).order_by("created_at", "id")
        synced = 0
        failed = 0
        skipped = 0

        for vendor in approved_vendors.iterator():
            if options["dry_run"]:
                skipped += 1
                self.stdout.write(f"Would sync approved vendor {vendor.id} ({vendor.business_name})")
                continue
            try:
                result = sync_vendor_to_marketplace(vendor)
            except Exception as exc:
                failed += 1
                self.stderr.write(f"Failed to sync vendor {vendor.id} ({vendor.business_name}): {exc}")
                continue

            if result.get("status") == "skipped":
                skipped += 1
                self.stdout.write(f"Skipped approved vendor {vendor.id} ({vendor.business_name})")
            else:
                synced += 1
                self.stdout.write(f"Synced approved vendor {vendor.id} ({vendor.business_name})")

        summary = f"synced={synced} failed={failed} skipped={skipped}"
        if failed:
            self.stdout.write(self.style.ERROR(summary))
            raise CommandError(f"Marketplace listing sync failed for {failed} vendor(s).")

        self.stdout.write(self.style.SUCCESS(summary))

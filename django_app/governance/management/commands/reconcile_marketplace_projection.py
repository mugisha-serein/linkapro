from django.core.management.base import BaseCommand

from django_app.governance.marketplace_reconciliation import reconcile_marketplace_projection


class Command(BaseCommand):
    help = "Reconcile FastAPI marketplace projection rows with approved complete Django vendors."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report reconciliation actions without applying them.")

    def handle(self, *args, **options):
        result = reconcile_marketplace_projection(dry_run=options["dry_run"])
        self.stdout.write(f"Django approved complete vendors: {result.django_approved_complete_count}")
        self.stdout.write(f"FastAPI marketplace listings: {result.fastapi_projection_count}")
        self.stdout.write(f"Stale FastAPI listings to delete: {result.stale_projection_count}")
        if result.dry_run:
            self.stdout.write("Dry run: no marketplace projection changes applied.")
        self.stdout.write(f"Deleted stale listings: {result.deleted_stale_count}")
        self.stdout.write(f"Upserted/enqueued listings: {result.upsert_enqueued_count}")
        self.stdout.write("Marketplace projection reconciliation completed.")

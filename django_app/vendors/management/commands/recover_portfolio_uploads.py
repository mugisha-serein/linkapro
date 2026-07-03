from django.core.management.base import BaseCommand

from django_app.vendors.portfolio_recovery import RECOVERY_CATEGORIES, recover_stuck_portfolio_media


class Command(BaseCommand):
    help = "Recover vendor portfolio media rows that are stuck after upload handoff failures."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report recoverable rows without changing data.")
        parser.add_argument("--limit", type=int, default=None, help="Maximum number of portfolio rows to scan.")

    def handle(self, *args, **options):
        summary = recover_stuck_portfolio_media(dry_run=options["dry_run"], limit=options["limit"])

        self.stdout.write(f"Dry run: {str(summary['dry_run']).lower()}")
        self.stdout.write(f"Scanned: {summary['scanned']}")
        for category in RECOVERY_CATEGORIES:
            self.stdout.write(f"{category}: {summary['categories'][category]}")
        self.stdout.write(f"Updated: {summary['updated']}")
        self.stdout.write(f"Queued: {summary['queued']}")
        self.stdout.write(f"Unrecoverable: {summary['unrecoverable']}")

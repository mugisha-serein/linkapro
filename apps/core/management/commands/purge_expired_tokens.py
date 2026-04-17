from django.core.management.base import BaseCommand
from datetime import datetime, timezone

from infrastructure.persistence.token_repository import TokenRepository
from infrastructure.persistence.revocation_store_impl import RevocationStoreImpl
from infrastructure.events.event_bus import EventBus

from domain.events.security_events import ExpiredTokensPurged


class Command(BaseCommand):
    help = "Purge expired authentication tokens and cleanup revoked entries"

    def handle(self, *args, **options):
        """
        CROSS-CUTTING MAINTENANCE COMMAND

        PURPOSE:
        - Remove expired access/refresh tokens
        - Clean revoked token store
        - Maintain storage hygiene
        - Emit audit event
        """

        self.stdout.write("Starting expired token purge job...")

        repo = TokenRepository()
        revocation_store = RevocationStoreImpl()
        bus = EventBus.get_instance()

        now = datetime.now(timezone.utc)

        try:
            # -----------------------------
            # 1. Find expired tokens
            # -----------------------------
            expired_tokens = repo.find_expired_tokens(now)

            # -----------------------------
            # 2. Delete expired tokens
            # -----------------------------
            deleted_count = repo.delete_expired_tokens(now)

            # -----------------------------
            # 3. Clean revocation store (optional TTL cleanup)
            # -----------------------------
            revoked_cleaned = revocation_store.cleanup_expired_entries(now)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Purged {deleted_count} expired tokens. "
                    f"Cleaned {revoked_cleaned} revoked entries."
                )
            )

            # -----------------------------
            # 4. Emit security/audit event
            # -----------------------------
            bus.publish(
                ExpiredTokensPurged(
                    expired_count=deleted_count,
                    revoked_cleaned=revoked_cleaned,
                    timestamp=now,
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Token purge failed: {str(e)}")
            )
            raise
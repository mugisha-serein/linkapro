from django.core.management.base import BaseCommand
from datetime import datetime

from infrastructure.token.key_store import KeyStore
from infrastructure.events.event_bus import EventBus
from domain.events.security_events import KeyRotationCompleted


class Command(BaseCommand):
    help = "Rotate authentication signing keys safely"

    def handle(self, *args, **options):
        """
        CROSS-CUTTING OPERATION

        PURPOSE:
        - Rotate signing keys used by TokenProvider
        - Maintain backward compatibility (if supported)
        - Emit security event after rotation
        """

        self.stdout.write("Starting key rotation process...")

        store = KeyStore()
        bus = EventBus.get_instance()

        try:
            # -----------------------------
            # 1. Generate new key pair
            # -----------------------------
            new_key_id = store.generate_new_key()

            # -----------------------------
            # 2. Promote new key to active
            # -----------------------------
            store.set_active_key(new_key_id)

            # -----------------------------
            # 3. Optionally mark old keys as deprecated
            # -----------------------------
            store.deprecate_old_keys()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Key rotation successful. Active key: {new_key_id}"
                )
            )

            # -----------------------------
            # 4. Emit domain event
            # -----------------------------
            bus.publish(
                KeyRotationCompleted(
                    key_id=new_key_id,
                    rotated_at=datetime.utcnow(),
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Key rotation failed: {str(e)}")
            )
            raise
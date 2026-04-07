"""
Django management command for JWT RSA key rotation.
Usage: python manage.py rotate_jwt_keys
"""

from django.core.management.base import BaseCommand
from apps.accounts.services.jwt_key_rotation import JWTKeyRotationManager


class Command(BaseCommand):
    help = 'Rotate JWT RSA keys with zero downtime'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rotation even if recently rotated'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old key files (keeps last 2 versions)'
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show current key version and status'
        )

    def handle(self, *args, **options):
        if options['status']:
            self._show_status()
        elif options['cleanup']:
            self._cleanup_old_keys()
        else:
            self._rotate_keys(force=options['force'])

    def _show_status(self):
        """Display current JWT key status."""
        current_version = JWTKeyRotationManager.get_current_version()
        valid_keys = JWTKeyRotationManager.get_all_valid_public_keys()

        self.stdout.write(self.style.SUCCESS('=== JWT Key Status ==='))
        self.stdout.write(f'Current version: {current_version}')
        self.stdout.write(f'Valid key versions: {list(valid_keys.keys())}')

    def _rotate_keys(self, force=False):
        """Perform JWT key rotation."""
        try:
            result = JWTKeyRotationManager.rotate_keys()
            self.stdout.write(self.style.SUCCESS('✓ Key rotation completed successfully'))
            self.stdout.write(f"  Old version: {result['old_version']}")
            self.stdout.write(f"  New version: {result['new_version']}")
            self.stdout.write(f"  Grace period: {result['grace_period_days']} days")
            self.stdout.write(self.style.WARNING(
                '\n⚠️  Restart Django and FastAPI services to load new keys'
            ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'✗ Key rotation failed: {exc}'))

    def _cleanup_old_keys(self):
        """Clean up old key files."""
        try:
            JWTKeyRotationManager.cleanup_old_keys(keep_versions=2)
            self.stdout.write(self.style.SUCCESS('✓ Old keys cleaned up'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'✗ Cleanup failed: {exc}'))

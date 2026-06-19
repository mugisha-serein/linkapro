from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django_app.common.redis_config import (
    get_redis_client,
    mask_redis_url,
    redis_uses_tls,
    validate_redis_url,
)


class Command(BaseCommand):
    help = "Validate Redis configuration without exposing credentials."

    def add_arguments(self, parser):
        parser.add_argument("--ping", action="store_true", help="Attempt Redis PING.")

    def handle(self, *args, **options):
        redis_url = validate_redis_url(getattr(settings, "REDIS_URL", ""), required=True)
        self.stdout.write(f"REDIS_URL={mask_redis_url(redis_url)}")
        self.stdout.write(f"TLS={'enabled' if redis_uses_tls(redis_url) else 'disabled'}")

        if options["ping"]:
            try:
                client = get_redis_client()
                client.ping()
            except Exception as exc:
                raise CommandError(f"Redis ping failed: {exc.__class__.__name__}") from exc
            self.stdout.write(self.style.SUCCESS("Redis ping succeeded."))
        else:
            self.stdout.write("Redis URL validation succeeded. Use --ping to test connectivity.")

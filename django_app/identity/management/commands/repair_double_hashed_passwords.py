from __future__ import annotations

import secrets
import string
from datetime import datetime, time

from django.contrib.auth.hashers import identify_hasher
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from django_app.identity.models import User


class Command(BaseCommand):
    help = (
        "Repair accounts likely affected by the historical double-hashing bug by "
        "assigning strong temporary passwords. Dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            action="append",
            dest="emails",
            default=[],
            help="Target a specific account email. Can be provided multiple times.",
        )
        parser.add_argument(
            "--before",
            type=str,
            help="Target accounts created on or before YYYY-MM-DD.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes. Without this flag the command only reports candidates.",
        )

    def handle(self, *args, **options):
        users = self._get_candidates(options["emails"], options.get("before"))
        if not users:
            self.stdout.write(self.style.WARNING("No matching password-based users found."))
            return

        self.stdout.write(f"Found {users.count()} candidate user(s).")
        if not options["apply"]:
            for user in users:
                self.stdout.write(
                    f"DRY RUN {user.email} created_at={user.created_at.isoformat()} password_usable={user.has_usable_password()}"
                )
            self.stdout.write("Run again with --apply to assign temporary passwords.")
            return

        for user in users:
            temp_password = self._generate_temp_password()
            user.set_password(temp_password)
            user.save(update_fields=["password"])
            self.stdout.write(
                self.style.SUCCESS(f"{user.email} temporary_password={temp_password}")
            )

    def _get_candidates(self, emails: list[str], before: str | None):
        queryset = User.objects.exclude(password__isnull=True).exclude(password="")

        if emails:
            queryset = queryset.filter(email__in=emails)

        if before:
            try:
                before_date = datetime.strptime(before, "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("--before must use YYYY-MM-DD") from exc
            cutoff = timezone.make_aware(datetime.combine(before_date, time.max))
            queryset = queryset.filter(created_at__lte=cutoff)

        filtered_ids = []
        for user in queryset:
            if not user.has_usable_password():
                continue
            try:
                identify_hasher(user.password)
            except ValueError:
                continue
            filtered_ids.append(user.id)

        return queryset.filter(id__in=filtered_ids).order_by("created_at", "email")

    @staticmethod
    def _generate_temp_password(length: int = 14) -> str:
        alphabet = string.ascii_letters + string.digits
        while True:
            password = "".join(secrets.choice(alphabet) for _ in range(length))
            if (
                any(ch.islower() for ch in password)
                and any(ch.isupper() for ch in password)
                and any(ch.isdigit() for ch in password)
            ):
                return password

import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from django_app.identity.models import User


class Command(BaseCommand):
    help = "Create or promote a LinkaPro application admin user safely."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Admin email address.")
        parser.add_argument("--first-name", default="Admin", help="Admin first name.")
        parser.add_argument("--last-name", default="User", help="Admin last name.")
        parser.add_argument(
            "--promote-existing",
            action="store_true",
            help="Promote an existing user with this email to app admin.",
        )
        parser.add_argument(
            "--password-env",
            help="Read the password from this environment variable for CI/staging one-time commands.",
        )

    def handle(self, *args, **options):
        email = User.objects.normalize_email(options["email"]).strip().lower()
        if not email:
            raise CommandError("--email is required.")

        existing = User.objects.filter(email=email).first()
        if existing and not options["promote_existing"]:
            raise CommandError("User already exists. Re-run with --promote-existing to promote intentionally.")

        password = self._read_password(options.get("password_env"))

        user_for_validation = existing or User(
            email=email,
            first_name=options["first_name"],
            last_name=options["last_name"],
            role=User.Role.ADMIN,
            is_staff=True,
        )
        try:
            validate_password(password, user=user_for_validation)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        user = existing or User(email=email)
        user.email = email
        user.first_name = options["first_name"]
        user.last_name = options["last_name"]
        user.role = User.Role.ADMIN
        user.is_staff = True
        user.is_superuser = False
        user.is_active = True
        user.is_verified = True
        user.set_password(password)
        user.save()

        action = "Promoted" if existing else "Created"
        self.stdout.write(self.style.SUCCESS(f"{action} LinkaPro app admin: {email}"))

    def _read_password(self, password_env: str | None) -> str:
        if password_env:
            password = os.environ.get(password_env)
            if not password:
                raise CommandError(f"Environment variable {password_env} is not set.")
            return password

        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Password (again): ")
        if password != confirm:
            raise CommandError("Passwords do not match.")
        if not password:
            raise CommandError("Password cannot be empty.")
        return password

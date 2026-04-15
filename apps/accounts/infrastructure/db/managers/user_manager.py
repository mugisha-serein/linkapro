from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _normalize_email_value(self, email: str) -> str:
        return self.normalize_email(email).strip().lower()

    def get_by_natural_key(self, email: str):
        return self.get(email=self._normalize_email_value(email))

    def filter_by_email(self, email: str):
        return self.filter(email=self._normalize_email_value(email))

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        email = self._normalize_email_value(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        email = self._normalize_email_value(email)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)
        if hasattr(self.model, "Role"):
            extra_fields.setdefault("role", self.model.Role.ADMIN)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

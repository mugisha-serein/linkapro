from django.contrib.auth.hashers import make_password, check_password
from domain.identity.value_objects import PlainPassword, PasswordHash


class DjangoPasswordHasher:
    def hash(self, plain: PlainPassword) -> str:
        return make_password(plain.value)

    def verify(self, plain: PlainPassword | str, hashed: PasswordHash) -> bool:
        candidate = plain.value if hasattr(plain, "value") else str(plain)
        return check_password(candidate, hashed.raw_value)

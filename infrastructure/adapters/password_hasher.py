from django.contrib.auth.hashers import make_password, check_password
from domain.identity.value_objects import PlainPassword, PasswordHash


class DjangoPasswordHasher:
    def hash(self, plain: PlainPassword) -> str:
        return make_password(plain.value)

    def verify(self, plain: PlainPassword, hashed: PasswordHash) -> bool:
        return check_password(plain.value, hashed.value)
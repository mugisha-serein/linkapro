from domain.identity.value_objects import PlainPassword, PasswordHash
from infrastructure.adapters.password_hasher import DjangoPasswordHasher

def test_hash_and_verify():
    hasher = DjangoPasswordHasher()
    plain = PlainPassword("MySecret123!")
    hashed_str = hasher.hash(plain)
    hashed = PasswordHash(hashed_str)

    assert hasher.verify(plain, hashed) is True
    assert hasher.verify(PlainPassword("WrongPass1!"), hashed) is False

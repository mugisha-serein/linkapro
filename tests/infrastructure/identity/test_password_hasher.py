from domain.identity.credentials import PasswordHash, PlainPassword
from infrastructure.identity.shared.security_primitives import DjangoPasswordHasher

def test_hash_and_verify():
    hasher = DjangoPasswordHasher()
    plain = PlainPassword("MySecret123!")
    hashed_str = hasher.hash(plain)
    hashed = PasswordHash(hashed_str)

    assert hasher.verify(plain, hashed) is True
    assert hasher.verify(PlainPassword("WrongPass1!"), hashed) is False


def test_verify_against_dummy_runs_without_returning_match():
    hasher = DjangoPasswordHasher()

    assert hasher.verify_against_dummy(PlainPassword("MySecret123!")) is None

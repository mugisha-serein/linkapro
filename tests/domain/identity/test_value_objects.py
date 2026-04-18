import pytest

from domain.identity.value_objects import (
    Email,
    PasswordHash,
    PlainPassword,
    InvalidEmailError,
    WeakPasswordError,
)


class TestEmail:
    def test_valid_email(self):
        email = Email("user@example.com")
        assert str(email) == "user@example.com"

    def test_invalid_email_raises_error(self):
        with pytest.raises(InvalidEmailError):
            Email("not-an-email")

    @pytest.mark.parametrize(
        "invalid",
        ["plain", "missing@tld", "@missing-user.com", "spaces in@email.com", ""],
    )
    def test_various_invalid_emails(self, invalid):
        with pytest.raises(InvalidEmailError):
            Email(invalid)


class TestPlainPassword:
    def test_strong_password_accepted(self):
        pwd = PlainPassword("StrongPass1")
        assert isinstance(pwd, PlainPassword)

    def test_too_short_raises_error(self):
        with pytest.raises(WeakPasswordError, match="at least 8 characters"):
            PlainPassword("Short1")

    def test_missing_uppercase_raises_error(self):
        with pytest.raises(WeakPasswordError, match="uppercase"):
            PlainPassword("nouppercase1")

    def test_missing_lowercase_raises_error(self):
        with pytest.raises(WeakPasswordError, match="lowercase"):
            PlainPassword("NOLOWERCASE1")

    def test_missing_digit_raises_error(self):
        with pytest.raises(WeakPasswordError, match="digit"):
            PlainPassword("NoDigitHere")

    def test_str_representation_is_masked(self):
        pwd = PlainPassword("Secret123")
        assert str(pwd) == "******"
import pytest

from domain.identity.value_objects import (
    Email,
    OAuthAccessToken,
    OAuthRefreshToken,
    PasswordHash,
    PlainPassword,
    TOTPSecret,
    InvalidEmailError,
    WeakPasswordError,
)


class TestEmail:
    def test_valid_email(self):
        email = Email("user@example.com")
        assert str(email) == "user@example.com"

    def test_email_is_normalized(self):
        email = Email(" USER@Example.COM ")
        assert email.value == "user@example.com"
        assert str(email) == "user@example.com"

    def test_invalid_email_raises_error(self):
        with pytest.raises(InvalidEmailError):
            Email("not-an-email")

    def test_invalid_email_error_does_not_expose_raw_email(self):
        raw_email = " not-an-email@example .com "
        with pytest.raises(InvalidEmailError) as exc_info:
            Email(raw_email)
        assert raw_email not in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid",
        ["plain", "missing@tld", "@missing-user.com", "spaces in@email.com", ""],
    )
    def test_various_invalid_emails(self, invalid):
        with pytest.raises(InvalidEmailError):
            Email(invalid)


class TestPlainPassword:
    def test_strong_password_accepted(self):
        pwd = PlainPassword("StrongPass1!")
        assert isinstance(pwd, PlainPassword)

    def test_too_short_raises_error(self):
        with pytest.raises(WeakPasswordError, match="at least 8 characters"):
            PlainPassword("Short1")

    def test_missing_uppercase_raises_error(self):
        with pytest.raises(WeakPasswordError, match="uppercase"):
            PlainPassword("nouppercase1!")

    def test_missing_lowercase_raises_error(self):
        with pytest.raises(WeakPasswordError, match="lowercase"):
            PlainPassword("NOLOWERCASE1!")

    def test_missing_digit_raises_error(self):
        with pytest.raises(WeakPasswordError, match="digit"):
            PlainPassword("NoDigitHere!")

    def test_missing_special_character_raises_error(self):
        with pytest.raises(WeakPasswordError, match="special character"):
            PlainPassword("NoSpecial1")

    def test_too_long_raises_error(self):
        with pytest.raises(WeakPasswordError, match="at most 128 characters"):
            PlainPassword("A1!" + "a" * 126)

    def test_str_representation_is_masked(self):
        pwd = PlainPassword("Secret123!")
        assert str(pwd) == "******"

    def test_repr_representation_is_masked(self):
        secret = "Secret123!"
        pwd = PlainPassword(secret)
        assert secret not in repr(pwd)


class TestPasswordHash:
    def test_str_and_repr_are_masked(self):
        secret_hash = "pbkdf2_sha256$secret_hash"
        password_hash = PasswordHash(secret_hash)
        assert str(password_hash) == "******"
        assert secret_hash not in repr(password_hash)

    def test_raw_value_is_explicit(self):
        secret_hash = "pbkdf2_sha256$secret_hash"
        password_hash = PasswordHash(secret_hash)
        assert password_hash.raw_value == secret_hash


class TestTOTPSecret:
    def test_normalizes_to_uppercase(self):
        secret = TOTPSecret("abcdabcdabcdabcd")
        assert secret.raw_value == "ABCDABCDABCDABCD"

    def test_too_short_secret_is_rejected(self):
        with pytest.raises(ValueError, match="at least 16 characters"):
            TOTPSecret("ABCDABCD")

    def test_str_and_repr_are_masked(self):
        secret = "JBSWY3DPEHPK3PXP"
        totp_secret = TOTPSecret(secret)
        assert str(totp_secret) == "******"
        assert secret not in repr(totp_secret)

    def test_raw_value_is_explicit(self):
        secret = "JBSWY3DPEHPK3PXP"
        totp_secret = TOTPSecret(secret)
        assert totp_secret.raw_value == secret
        assert totp_secret.reveal() == secret
        assert totp_secret.reveal_for_totp_verification() == secret


class TestOAuthTokenValues:
    @pytest.mark.parametrize("token_cls", [OAuthAccessToken, OAuthRefreshToken])
    def test_str_and_repr_are_masked(self, token_cls):
        secret = "oauth-secret"
        token = token_cls(secret)
        assert str(token) == "******"
        assert secret not in repr(token)
        assert token.raw_value == secret

    @pytest.mark.parametrize("token_cls", [OAuthAccessToken, OAuthRefreshToken])
    def test_empty_values_are_rejected(self, token_cls):
        with pytest.raises(ValueError, match="cannot be empty"):
            token_cls("")

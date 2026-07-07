import pytest

from domain.identity.value_objects import (
    ApprovedPasswordChange,
    Email,
    OAuthAccessToken,
    OAuthRefreshToken,
    PasswordHash,
    PersonName,
    PlainPassword,
    SecurityReason,
    TOTPSecret,
    InvalidEmailError,
    InvalidSecurityReasonError,
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


class TestPersonName:
    def test_strips_names(self):
        name = PersonName(" John ", " Doe ")
        assert name.first_name == "John"
        assert name.last_name == "Doe"

    def test_full_name(self):
        name = PersonName("John", "Doe")
        assert name.full_name == "John Doe"

    @pytest.mark.parametrize(
        ("first_name", "last_name"),
        [("", "Doe"), ("   ", "Doe"), ("John", ""), ("John", "   ")],
    )
    def test_rejects_empty_names(self, first_name, last_name):
        with pytest.raises(ValueError, match="cannot be empty"):
            PersonName(first_name, last_name)


class TestPlainPassword:
    def test_accepts_long_passphrase_containing_spaces(self):
        pwd = PlainPassword("this is a long passphrase with spaces")
        assert isinstance(pwd, PlainPassword)

    def test_accepts_printable_unicode(self):
        pwd = PlainPassword("correct horse staplé 京都")
        assert pwd.reveal_for_password_hashing() == "correct horse staplé 京都"

    def test_does_not_require_uppercase(self):
        assert PlainPassword("lowercase only passphrase")

    def test_does_not_require_lowercase(self):
        assert PlainPassword("UPPERCASE ONLY PASSPHRASE")

    def test_does_not_require_digits(self):
        assert PlainPassword("No digits needed here")

    def test_does_not_require_symbols(self):
        assert PlainPassword("NoSymbolsOrDigits")

    def test_empty_password_raises_error(self):
        with pytest.raises(WeakPasswordError, match="empty"):
            PlainPassword("")

    def test_unsafe_control_character_raises_error(self):
        with pytest.raises(WeakPasswordError, match="control"):
            PlainPassword("unsafe\npassword")

    def test_too_long_raises_error(self):
        with pytest.raises(WeakPasswordError, match="128"):
            PlainPassword("a" * 129)

    def test_str_representation_is_masked(self):
        pwd = PlainPassword("Secret123")
        assert str(pwd) == "******"

    def test_repr_representation_is_masked(self):
        pwd = PlainPassword("Secret123")
        assert "Secret123" not in repr(pwd)
        assert "******" in repr(pwd)

    def test_reveal_for_password_hashing_returns_value_intentionally(self):
        pwd = PlainPassword("Secret123")
        assert pwd.reveal_for_password_hashing() == "Secret123"


class TestApprovedPasswordChange:
    def test_rejects_missing_blocklist_check(self):
        with pytest.raises(ValueError, match="blocklist"):
            ApprovedPasswordChange(
                new_password_hash=PasswordHash("hashed"),
                blocklist_checked=False,
                reuse_checked=True,
            )

    def test_rejects_missing_reuse_check_for_password_change_flow(self):
        with pytest.raises(ValueError, match="reuse"):
            ApprovedPasswordChange(
                new_password_hash=PasswordHash("hashed"),
                blocklist_checked=True,
                reuse_checked=False,
            )

    def test_accepts_fully_approved_password_hash(self):
        approved = ApprovedPasswordChange(
            new_password_hash=PasswordHash("hashed"),
            blocklist_checked=True,
            reuse_checked=True,
        )
        assert approved.new_password_hash == PasswordHash("hashed")

    def test_accepts_missing_reuse_check_when_not_required(self):
        approved = ApprovedPasswordChange(
            new_password_hash=PasswordHash("hashed"),
            blocklist_checked=True,
            reuse_checked=False,
            reuse_check_required=False,
        )
        assert approved.reuse_check_required is False

    def test_repr_masks_hash(self):
        approved = ApprovedPasswordChange(
            new_password_hash=PasswordHash("hashed-secret"),
            blocklist_checked=True,
            reuse_checked=True,
        )
        assert "hashed-secret" not in repr(approved)
        assert "******" in repr(approved)
    def test_strong_password_accepted(self):
        pwd = PlainPassword("StrongPass1!")
        assert isinstance(pwd, PlainPassword)

    def test_password_with_trailing_whitespace_is_rejected(self):
        with pytest.raises(WeakPasswordError, match="whitespace"):
            PlainPassword("Password1 ")

    def test_password_with_leading_whitespace_is_rejected(self):
        with pytest.raises(WeakPasswordError, match="whitespace"):
            PlainPassword(" Password1!")

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

    def test_whitespace_cannot_satisfy_special_character_rule(self):
        with pytest.raises(WeakPasswordError):
            PlainPassword("Password1 ")

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

    def test_str_and_repr_do_not_expose_secret(self):
        secret = "Password1!"
        password = PlainPassword(secret)
        assert secret not in str(password)
        assert secret not in repr(password)

    @pytest.mark.parametrize("secret", ["Password1!\n", "Password1!\r", "Pass\tword1!", "Password1!\x00"])
    def test_control_characters_are_rejected(self, secret):
        with pytest.raises(WeakPasswordError) as exc_info:
            PlainPassword(secret)
        assert secret not in str(exc_info.value)

    def test_fingerprint_does_not_expose_secret(self):
        secret = "Password1!"
        password = PlainPassword(secret)
        assert password.fingerprint().startswith("sha256:")
        assert secret not in password.fingerprint()


class TestPasswordHash:
    def test_str_and_repr_are_masked(self):
        secret_hash = "pbkdf2_sha256$secret_hash"
        password_hash = PasswordHash(secret_hash)
        assert str(password_hash) == "******"
        assert secret_hash not in repr(password_hash)

    def test_purpose_specific_reveal_is_explicit(self):
        secret_hash = "pbkdf2_sha256$secret_hash"
        password_hash = PasswordHash(secret_hash)
        assert password_hash.reveal_for_password_verification() == secret_hash

    @pytest.mark.parametrize("secret_hash", ["hash\nvalue", "hash\rvalue", "hash\tvalue", "hash\x00value"])
    def test_control_characters_are_rejected(self, secret_hash):
        with pytest.raises(ValueError) as exc_info:
            PasswordHash(secret_hash)
        assert secret_hash not in str(exc_info.value)

    def test_fingerprint_is_stable_and_non_reversible(self):
        secret_hash = "pbkdf2_sha256$secret_hash"
        same = PasswordHash(secret_hash)
        duplicate = PasswordHash(secret_hash)
        different = PasswordHash("pbkdf2_sha256$other_hash")
        assert same.fingerprint().startswith("sha256:")
        assert secret_hash not in same.fingerprint()
        assert same.fingerprint() == duplicate.fingerprint()
        assert same.fingerprint() != different.fingerprint()


class TestTOTPSecret:
    def test_normalizes_to_uppercase(self):
        secret = TOTPSecret("abcdabcdabcdabcd")
        assert secret.reveal_for_totp_verification() == "ABCDABCDABCDABCD"

    def test_too_short_secret_is_rejected(self):
        with pytest.raises(ValueError, match="at least 16 characters"):
            TOTPSecret("ABCDABCD")

    @pytest.mark.parametrize(
        "secret",
        [
            "ABCDABCDABCDABC=",
            "ABCDABCDABCDABCD===",
            "JBSWY3DPEHPK3PX0",
        ],
    )
    def test_malformed_base32_secret_is_rejected(self, secret):
        with pytest.raises(ValueError, match="Invalid TOTP secret format"):
            TOTPSecret(secret)

    def test_str_and_repr_are_masked(self):
        secret = "JBSWY3DPEHPK3PXP"
        totp_secret = TOTPSecret(secret)
        assert str(totp_secret) == "******"
        assert secret not in repr(totp_secret)
        assert secret not in str(totp_secret)

    def test_purpose_specific_reveal_is_explicit(self):
        secret = "JBSWY3DPEHPK3PXP"
        totp_secret = TOTPSecret(secret)
        assert totp_secret.reveal_for_totp_verification() == secret

    @pytest.mark.parametrize(
        "secret",
        ["JBSWY3DPEHPK3PXP\n", "JBSWY3DPEHPK3PXP\r", "JBSWY3DPEHPK3PXP\t", "JBSWY3DPEHPK3PXP\x00"],
    )
    def test_control_characters_are_rejected(self, secret):
        with pytest.raises(ValueError) as exc_info:
            TOTPSecret(secret)
        assert secret not in str(exc_info.value)

    def test_fingerprint_does_not_expose_secret(self):
        secret = "JBSWY3DPEHPK3PXP"
        totp_secret = TOTPSecret(secret)
        assert totp_secret.fingerprint().startswith("sha256:")
        assert secret not in totp_secret.fingerprint()


class TestOAuthTokenValues:
    @pytest.mark.parametrize("token_cls", [OAuthAccessToken, OAuthRefreshToken])
    def test_str_and_repr_are_masked(self, token_cls):
        secret = "oauth-secret"
        token = token_cls(secret)
        assert str(token) == "******"
        assert secret not in str(token)
        assert secret not in repr(token)
        assert token.reveal_for_provider_sync() == secret

    @pytest.mark.parametrize("token_cls", [OAuthAccessToken, OAuthRefreshToken])
    def test_empty_values_are_rejected(self, token_cls):
        with pytest.raises(ValueError, match="cannot be empty"):
            token_cls("")

    @pytest.mark.parametrize("token_cls", [OAuthAccessToken, OAuthRefreshToken])
    @pytest.mark.parametrize("secret", ["oauth\nsecret", "oauth\rsecret", "oauth\tsecret", "oauth\x00secret"])
    def test_control_characters_are_rejected(self, token_cls, secret):
        with pytest.raises(ValueError) as exc_info:
            token_cls(secret)
        assert secret not in str(exc_info.value)

    @pytest.mark.parametrize("token_cls", [OAuthAccessToken, OAuthRefreshToken])
    def test_fingerprint_is_stable_and_non_reversible(self, token_cls):
        secret = "oauth-secret"
        same = token_cls(secret)
        duplicate = token_cls(secret)
        different = token_cls("different-oauth-secret")
        assert same.fingerprint().startswith("sha256:")
        assert secret not in same.fingerprint()
        assert same.fingerprint() == duplicate.fingerprint()
        assert same.fingerprint() != different.fingerprint()


class TestSecurityReason:
    def test_reason_is_normalized(self):
        reason = SecurityReason(" User requested account closure ")
        assert str(reason) == "User requested account closure"

    @pytest.mark.parametrize(
        "reason",
        ["", "   ", "contains password", "contains token", "contains secret", "contains totp", "contains refresh"],
    )
    def test_empty_or_secret_like_reason_is_rejected(self, reason):
        with pytest.raises(InvalidSecurityReasonError):
            SecurityReason(reason)

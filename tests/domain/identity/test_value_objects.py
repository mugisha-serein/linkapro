import pytest

from domain.identity.value_objects import (
    ApprovedPasswordChange,
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

from domain.identity.password_policy import (
    PasswordPolicy,
    PasswordPolicyContext,
    PasswordRejectionReason,
)
from domain.identity.value_objects import Email, PlainPassword


class BlocklistStub:
    def __init__(
        self,
        *,
        common: bool = False,
        compromised: bool = False,
        context_specific: bool = False,
    ):
        self.common = common
        self.compromised = compromised
        self.context_specific = context_specific
        self.context_email = None
        self.context_service_name = None

    def is_common_password(self, password: PlainPassword) -> bool:
        return self.common

    def is_compromised_password(self, password: PlainPassword) -> bool:
        return self.compromised

    def is_context_specific_password(
        self,
        password: PlainPassword,
        *,
        email: Email | None = None,
        service_name: str | None = None,
    ) -> bool:
        self.context_email = email
        self.context_service_name = service_name
        return self.context_specific


class ReuseCheckerStub:
    def __init__(self, *, reused: bool = False):
        self.reused = reused

    def is_reused_password(self, password: PlainPassword) -> bool:
        return self.reused


class OversizedPassword:
    def reveal_for_password_hashing(self) -> str:
        return "a" * 129


class TestPasswordPolicy:
    def test_requires_at_least_15_characters_without_mfa(self):
        decision = PasswordPolicy().evaluate(
            PlainPassword("short-pass"),
            PasswordPolicyContext(mfa_enabled=False),
        )

        assert decision.approved is False
        assert PasswordRejectionReason.TOO_SHORT in decision.rejection_reasons

    def test_permits_at_least_8_characters_when_mfa_enabled(self):
        decision = PasswordPolicy().evaluate(
            PlainPassword("eight888"),
            PasswordPolicyContext(mfa_enabled=True),
        )

        assert decision.approved is True
        assert decision.rejection_reasons == ()

    def test_rejects_passwords_longer_than_128(self):
        decision = PasswordPolicy().evaluate(
            OversizedPassword(),
            PasswordPolicyContext(mfa_enabled=True),
        )

        assert decision.approved is False
        assert PasswordRejectionReason.TOO_LONG in decision.rejection_reasons

    def test_rejects_blocklisted_password(self):
        decision = PasswordPolicy().evaluate(
            PlainPassword("acceptable length password"),
            PasswordPolicyContext(mfa_enabled=False),
            blocklist=BlocklistStub(common=True),
        )

        assert PasswordRejectionReason.COMMON_PASSWORD in decision.rejection_reasons
        assert decision.blocklist_checked is True

    def test_rejects_compromised_password(self):
        decision = PasswordPolicy().evaluate(
            PlainPassword("acceptable length password"),
            PasswordPolicyContext(mfa_enabled=False),
            blocklist=BlocklistStub(compromised=True),
        )

        assert PasswordRejectionReason.COMPROMISED_PASSWORD in decision.rejection_reasons

    def test_rejects_context_specific_password_from_email_or_service(self):
        email = Email("person@example.com")
        blocklist = BlocklistStub(context_specific=True)

        decision = PasswordPolicy().evaluate(
            PlainPassword("acceptable length password"),
            PasswordPolicyContext(
                mfa_enabled=False,
                email=email,
                service_name="LinkaPro",
            ),
            blocklist=blocklist,
        )

        assert PasswordRejectionReason.CONTEXT_SPECIFIC in decision.rejection_reasons
        assert blocklist.context_email == email
        assert blocklist.context_service_name == "LinkaPro"

    def test_rejects_recently_reused_password(self):
        decision = PasswordPolicy().evaluate(
            PlainPassword("acceptable length password"),
            PasswordPolicyContext(mfa_enabled=False),
            reuse_checker=ReuseCheckerStub(reused=True),
        )

        assert PasswordRejectionReason.REUSED_PASSWORD in decision.rejection_reasons
        assert decision.reuse_checked is True

    def test_returns_structured_rejection_reason(self):
        decision = PasswordPolicy().evaluate(
            PlainPassword("short"),
            PasswordPolicyContext(mfa_enabled=False),
        )

        assert decision.rejection_reasons == (PasswordRejectionReason.TOO_SHORT,)

    def test_decision_never_includes_plaintext_password(self):
        plaintext = "plain secret passphrase"
        decision = PasswordPolicy().evaluate(
            PlainPassword(plaintext),
            PasswordPolicyContext(mfa_enabled=False),
            blocklist=BlocklistStub(common=True),
            reuse_checker=ReuseCheckerStub(reused=True),
        )

        assert plaintext not in repr(decision)
        assert plaintext not in str(decision)

"""Complete a password login that requires MFA."""

from .authenticated_session_issuer import AuthenticationDecision, AuthenticationStatus, AuthenticatedSessionIssuer
from application.identity.authentication.complete_mfa_login_command import LoginTwoFactorCommand
from application.identity.mfa.consume_recovery_code import ConsumeRecoveryCodeCommand, ConsumeRecoveryCodeUseCase
from application.identity.shared.ports import (
    AccountRepository,
    EventOutbox,
    MfaChallengeRepository,
    MfaReplayStore,
    TokenRevocationStore,
    TotpSecretRepository,
    TotpService,
)
from domain.identity.mfa import MfaChallengeExpired, MfaPolicy
from domain.shared.utils import utc_now


class CompleteMfaLoginUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        totp_secret_repository: TotpSecretRepository,
        token_service,
        token_blacklist: TokenRevocationStore,
        mfa_challenge_repository: MfaChallengeRepository,
        mfa_replay_store: MfaReplayStore,
        totp_service: TotpService,
        consume_recovery_code_use_case: ConsumeRecoveryCodeUseCase,
        event_outbox: EventOutbox,
        session_issuer: AuthenticatedSessionIssuer,
        mfa_policy: MfaPolicy | None = None,
    ) -> None:
        self.account_repository = account_repository
        self.totp_secret_repository = totp_secret_repository
        self.token_service = token_service
        self.token_blacklist = token_blacklist
        self.mfa_challenge_repository = mfa_challenge_repository
        self.mfa_replay_store = mfa_replay_store
        self.totp_service = totp_service
        self.consume_recovery_code_use_case = consume_recovery_code_use_case
        self.session_issuer = session_issuer
        self.event_outbox = event_outbox
        self.mfa_policy = mfa_policy or MfaPolicy()

    def execute(self, cmd: LoginTwoFactorCommand) -> AuthenticationDecision:
        grant = self.token_service.inspect_mfa_login_grant(cmd.temp_token)
        if not grant:
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_TEMP_TOKEN)

        if self.token_blacklist.is_mfa_grant_blacklisted(grant):
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_TEMP_TOKEN)

        user = self.account_repository.get_by_id(grant.account_id)
        if not user or not user.is_active:
            return AuthenticationDecision(
                status=AuthenticationStatus.INACTIVE
                if user and not user.is_active
                else AuthenticationStatus.INVALID_TEMP_TOKEN
            )

        secret = self.totp_secret_repository.get_totp_secret(user.id)
        if not secret:
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_TEMP_TOKEN)

        challenge = self.mfa_challenge_repository.get(grant.challenge_id)
        if challenge is None or challenge.user_id != user.id:
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_TEMP_TOKEN)

        now = utc_now()
        totp_accepted = self.totp_service.verify(secret, cmd.token, now=now)
        recovery_accepted = False
        if not totp_accepted and _challenge_can_attempt(challenge, now=now):
            recovery_accepted = self.consume_recovery_code_use_case.execute(
                ConsumeRecoveryCodeCommand(user_id=user.id, code=cmd.token)
            )
        result = self.mfa_policy.verify_challenge(
            challenge=challenge,
            accepted=totp_accepted or recovery_accepted,
            now=now,
        )
        if not result.accepted:
            self.mfa_challenge_repository.save(result.challenge)
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_MFA_CODE)
        if totp_accepted and self.mfa_replay_store.has_been_used(challenge.id, cmd.token):
            return AuthenticationDecision(status=AuthenticationStatus.INVALID_MFA_CODE)
        if totp_accepted:
            self.mfa_replay_store.mark_used(
                challenge.id,
                cmd.token,
                ttl=self.mfa_policy.remaining_challenge_ttl_seconds(challenge, now=now),
            )
        self.mfa_challenge_repository.save(result.challenge)

        user.record_login()
        self.account_repository.save(user)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)

        decision = self.session_issuer.issue_authenticated_login(user)
        self.token_blacklist.blacklist_mfa_grant(grant)
        return decision


__all__ = ["CompleteMfaLoginUseCase"]


def _challenge_can_attempt(challenge, *, now) -> bool:
    try:
        return challenge.can_attempt(now=now)
    except MfaChallengeExpired:
        return False

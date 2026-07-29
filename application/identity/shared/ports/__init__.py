"""Shared identity ports used by application orchestration."""

from .account_repository import AccountRepository
from .authentication_attempt_repository import AuthenticationAttemptRepository
from .clock import Clock
from .email_verification_sender import EmailVerificationSender
from .event_outbox import EventOutbox
from .id_generator import IdGenerator
from .mfa_challenge_repository import MfaChallengeRepository
from .mfa_challenge_store import MfaReplayStore
from .mfa_enrollment_repository import MfaEnrollmentRepository, MfaEnrollmentState
from .mfa_recovery_code_repository import MfaRecoveryCodeRepository
from .oauth_identity_repository import OAuthIdentityRepository
from .password_history_repository import PasswordHistoryRepository
from .password_hasher import PasswordHasher
from .password_reset_repository import PasswordResetRepository, PasswordResetVerification
from .recovery_code_generator import RecoveryCodeGenerator
from .recovery_code_hasher import RecoveryCodeHasher
from .session_bootstrap_reader import SessionBootstrapReader
from .session_repository import AUTH_TOKEN_VERSION_CLAIM, SESSION_ID_CLAIM, SessionRepository
from .session_security_state_reader import SessionSecurityStateReader
from .step_up_grant_verifier import StepUpGrantVerifier
from .token_revocation_store import TokenRevocationStore
from .token_family_repository import TokenFamilyRepository
from application.identity.shared.dtos.token_claims import (
    AccessTokenClaims,
    IssuedTokenPair,
    RefreshTokenClaims,
    RotatedTokenPairRequest,
    StepUpTokenRequest,
    TokenBootstrapClaims,
    TokenClaims,
    MfaLoginGrant,
)
from .token_service import IdentityTokenService
from .totp_secret_repository import TotpSecretRepository
from .totp_service import TotpService
from .unit_of_work import IdentityUnitOfWork, NullIdentityUnitOfWork
from .verification_challenge_repository import VerificationChallengeRepository

__all__ = [
    "AUTH_TOKEN_VERSION_CLAIM",
    "AccessTokenClaims",
    "AuthenticationAttemptRepository",
    "Clock",
    "EmailVerificationSender",
    "EventOutbox",
    "IdGenerator",
    "IdentityTokenService",
    "IdentityUnitOfWork",
    "OAuthIdentityRepository",
    "SessionRepository",
    "TotpSecretRepository",
    "TokenRevocationStore",
    "IssuedTokenPair",
    "AccountRepository",
    "MfaEnrollmentRepository",
    "MfaEnrollmentState",
    "MfaRecoveryCodeRepository",
    "MfaChallengeRepository",
    "MfaLoginGrant",
    "MfaReplayStore",
    "NullIdentityUnitOfWork",
    "PasswordHistoryRepository",
    "PasswordHasher",
    "PasswordResetRepository",
    "PasswordResetVerification",
    "RefreshTokenClaims",
    "RecoveryCodeGenerator",
    "RecoveryCodeHasher",
    "RotatedTokenPairRequest",
    "SESSION_ID_CLAIM",
    "SessionBootstrapReader",
    "StepUpTokenRequest",
    "StepUpGrantVerifier",
    "SessionSecurityStateReader",
    "TokenBootstrapClaims",
    "TokenClaims",
    "TokenFamilyRepository",
    "TotpService",
    "VerificationChallengeRepository",
]

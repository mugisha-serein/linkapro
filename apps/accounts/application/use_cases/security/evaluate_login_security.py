# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from apps.accounts.application.dto.security_dto import EvaluateLoginSecurityCommand, EvaluateLoginSecurityResult
from apps.accounts.infrastructure.db.models import DeviceFingerprint, LoginActivity, User, UserSession
from apps.accounts.infrastructure.db.repositories import (
    DeviceRepository,
    LoginActivityRepository,
    SessionRepository,
    UserRepository,
)


@dataclass(slots=True)
class EvaluateLoginSecurityUseCase:
    user_repository: UserRepository
    device_repository: DeviceRepository
    session_repository: SessionRepository
    login_activity_repository: LoginActivityRepository

    def execute(self, command: EvaluateLoginSecurityCommand) -> EvaluateLoginSecurityResult:
        try:
            user_id = UUID(command.user_id)
        except ValueError:
            return EvaluateLoginSecurityResult(
                risk_score=100,
                risk_level="CRITICAL",
                flags=["INVALID_USER_ID"],
                recommendations=["Reject login attempt"],
                allow_login=False,
            )

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            return EvaluateLoginSecurityResult(
                risk_score=100,
                risk_level="CRITICAL",
                flags=["USER_NOT_FOUND"],
                recommendations=["Reject login attempt"],
                allow_login=False,
            )

        risk_score = 0
        flags = []
        recommendations = []

        # Evaluate device consistency
        device_risk = self._evaluate_device_consistency(user, command)
        risk_score += device_risk["score"]
        flags.extend(device_risk["flags"])

        # Evaluate geographic anomalies
        geo_risk = self._evaluate_geographic_anomalies(user, command)
        risk_score += geo_risk["score"]
        flags.extend(geo_risk["flags"])

        # Evaluate timing patterns
        timing_risk = self._evaluate_timing_patterns(user, command)
        risk_score += timing_risk["score"]
        flags.extend(timing_risk["flags"])

        # Evaluate account status
        account_risk = self._evaluate_account_status(user)
        risk_score += account_risk["score"]
        flags.extend(account_risk["flags"])

        # Determine risk level and recommendations
        risk_level, allow_login, final_recommendations = self._determine_risk_level(risk_score, flags)
        recommendations.extend(final_recommendations)

        return EvaluateLoginSecurityResult(
            risk_score=min(risk_score, 100),  # Cap at 100
            risk_level=risk_level,
            flags=flags,
            recommendations=recommendations,
            allow_login=allow_login,
        )

    def __call__(self, command: EvaluateLoginSecurityCommand) -> EvaluateLoginSecurityResult:
        return self.execute(command)

    def _evaluate_device_consistency(self, user: User, command: EvaluateLoginSecurityCommand) -> dict:
        score = 0
        flags = []

        # Check if device fingerprint exists
        existing_device = self.device_repository.get_by_user_and_fingerprint_hash(
            user_id=user.id,
            fingerprint_hash=command.fingerprint_hash,
        )

        if existing_device is None:
            score += 30
            flags.append("NEW_DEVICE")
        else:
            # Check for device attribute changes
            if existing_device.user_agent != command.user_agent:
                score += 15
                flags.append("USER_AGENT_CHANGED")

            if existing_device.ip_address != command.ip_address:
                score += 10
                flags.append("IP_ADDRESS_CHANGED")

        return {"score": score, "flags": flags}

    def _evaluate_geographic_anomalies(self, user: User, command: EvaluateLoginSecurityCommand) -> dict:
        score = 0
        flags = []

        if command.country_code:
            # Get recent login activities for this user
            recent_activities = self.login_activity_repository.list_for_user(user.id)[:10]

            known_countries = {activity.country_code for activity in recent_activities if activity.country_code}

            if command.country_code not in known_countries and known_countries:
                score += 25
                flags.append("UNUSUAL_COUNTRY")
            elif not known_countries:
                # First login, can't evaluate
                pass

        return {"score": score, "flags": flags}

    def _evaluate_timing_patterns(self, user: User, command: EvaluateLoginSecurityCommand) -> dict:
        score = 0
        flags = []

        # Check for rapid successive login attempts
        recent_activities = self.login_activity_repository.list_for_user(user.id)[:20]
        failed_count = sum(1 for activity in recent_activities
                          if activity.status == LoginActivity.Status.FAILED)

        if failed_count > 3:
            score += 20
            flags.append("RAPID_FAILED_ATTEMPTS")

        return {"score": score, "flags": flags}

    def _evaluate_account_status(self, user: User) -> dict:
        score = 0
        flags = []

        if not user.is_active:
            score += 100
            flags.append("ACCOUNT_INACTIVE")

        if user.failed_login_count > 5:
            score += 15
            flags.append("HIGH_FAILED_LOGIN_COUNT")

        return {"score": score, "flags": flags}

    def _determine_risk_level(self, score: int, flags: list[str]) -> tuple[str, bool, list[str]]:
        if score >= 80 or "ACCOUNT_INACTIVE" in flags:
            return "CRITICAL", False, ["Block login", "Require account verification"]
        elif score >= 60:
            return "HIGH", False, ["Require additional verification", "Send security alert"]
        elif score >= 40:
            return "MEDIUM", True, ["Monitor session closely", "Log security event"]
        elif score >= 20:
            return "LOW", True, ["Log for review"]
        else:
            return "SAFE", True, []
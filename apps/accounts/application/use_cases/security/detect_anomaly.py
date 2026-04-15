# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID
from datetime import timedelta

from django.utils import timezone

from apps.accounts.application.dto.security_dto import DetectAnomalyCommand, DetectAnomalyResult
from apps.accounts.infrastructure.db.models import LoginActivity, UserSession
from apps.accounts.infrastructure.db.repositories import (
    LoginActivityRepository,
    SessionRepository,
)


@dataclass(slots=True)
class DetectAnomalyUseCase:
    login_activity_repository: LoginActivityRepository
    session_repository: SessionRepository

    def execute(self, command: DetectAnomalyCommand) -> DetectAnomalyResult:
        try:
            user_id = UUID(command.user_id)
        except ValueError:
            return DetectAnomalyResult(
                is_anomalous=True,
                anomaly_score=1.0,
                anomaly_type="INVALID_INPUT",
                confidence=1.0,
                details={"error": "Invalid user ID format"},
            )

        # Get user's recent activity
        recent_activities = self.login_activity_repository.list_for_user(user_id)[:50]

        if not recent_activities:
            # New user, no anomaly detection possible
            return DetectAnomalyResult(
                is_anomalous=False,
                anomaly_score=0.0,
                anomaly_type=None,
                confidence=0.0,
                details={"reason": "No historical data"},
            )

        anomalies = []
        total_score = 0.0
        total_confidence = 0.0
        anomaly_count = 0

        # Check for IP address anomalies
        ip_anomaly = self._detect_ip_anomaly(command, recent_activities)
        if ip_anomaly["is_anomalous"]:
            anomalies.append(ip_anomaly)
            total_score += ip_anomaly["score"]
            total_confidence += ip_anomaly["confidence"]
            anomaly_count += 1

        # Check for timing anomalies
        timing_anomaly = self._detect_timing_anomaly(command, recent_activities)
        if timing_anomaly["is_anomalous"]:
            anomalies.append(timing_anomaly)
            total_score += timing_anomaly["score"]
            total_confidence += timing_anomaly["confidence"]
            anomaly_count += 1

        # Check for device anomalies
        device_anomaly = self._detect_device_anomaly(command, recent_activities)
        if device_anomaly["is_anomalous"]:
            anomalies.append(device_anomaly)
            total_score += device_anomaly["score"]
            total_confidence += device_anomaly["confidence"]
            anomaly_count += 1

        # Check for session anomalies
        session_anomaly = self._detect_session_anomaly(command, user_id)
        if session_anomaly["is_anomalous"]:
            anomalies.append(session_anomaly)
            total_score += session_anomaly["score"]
            total_confidence += session_anomaly["confidence"]
            anomaly_count += 1

        # Calculate overall anomaly score
        if anomaly_count > 0:
            avg_score = total_score / anomaly_count
            avg_confidence = total_confidence / anomaly_count

            # Determine primary anomaly type
            primary_anomaly = max(anomalies, key=lambda x: x["score"])

            return DetectAnomalyResult(
                is_anomalous=True,
                anomaly_score=min(avg_score, 1.0),
                anomaly_type=primary_anomaly["type"],
                confidence=min(avg_confidence, 1.0),
                details={
                    "anomalies_detected": anomaly_count,
                    "anomaly_types": [a["type"] for a in anomalies],
                    "individual_scores": {a["type"]: a["score"] for a in anomalies},
                },
            )
        else:
            return DetectAnomalyResult(
                is_anomalous=False,
                anomaly_score=0.0,
                anomaly_type=None,
                confidence=0.0,
                details={"anomalies_detected": 0},
            )

    def __call__(self, command: DetectAnomalyCommand) -> DetectAnomalyResult:
        return self.execute(command)

    def _detect_ip_anomaly(self, command: DetectAnomalyCommand, recent_activities) -> dict:
        # Extract IP addresses from recent activities
        recent_ips = {activity.ip_hash for activity in recent_activities if activity.ip_hash}

        # Simple hash of current IP for comparison
        current_ip_hash = self._hash_ip(command.ip_address)

        if current_ip_hash not in recent_ips and recent_ips:
            # IP not seen before
            return {
                "is_anomalous": True,
                "type": "UNSEEN_IP",
                "score": 0.7,
                "confidence": 0.8,
                "details": {"unseen_ip": True, "known_ips_count": len(recent_ips)},
            }

        return {"is_anomalous": False, "type": None, "score": 0.0, "confidence": 0.0}

    def _detect_timing_anomaly(self, command: DetectAnomalyCommand, recent_activities) -> dict:
        now = timezone.now()

        # Check for unusual login times
        current_hour = now.hour

        # Get login hours from recent activities
        login_hours = [activity.created_at.hour for activity in recent_activities
                      if activity.event_type == LoginActivity.EventType.LOGIN]

        if login_hours:
            avg_hour = sum(login_hours) / len(login_hours)
            hour_diff = abs(current_hour - avg_hour)

            # If login is more than 8 hours from average, flag as anomalous
            if hour_diff > 8:
                return {
                    "is_anomalous": True,
                    "type": "UNUSUAL_TIME",
                    "score": 0.5,
                    "confidence": 0.6,
                    "details": {"current_hour": current_hour, "avg_hour": avg_hour, "diff": hour_diff},
                }

        return {"is_anomalous": False, "type": None, "score": 0.0, "confidence": 0.0}

    def _detect_device_anomaly(self, command: DetectAnomalyCommand, recent_activities) -> dict:
        if not command.device_fingerprint:
            return {"is_anomalous": False, "type": None, "score": 0.0, "confidence": 0.0}

        # Check if device fingerprint has been seen before
        # This is a simplified check - in reality you'd compare against stored device fingerprints
        recent_devices = {activity.device for activity in recent_activities if activity.device}

        if not recent_devices:
            # No device history
            return {"is_anomalous": False, "type": None, "score": 0.0, "confidence": 0.0}

        # For now, assume any device change is moderately anomalous
        # In a real implementation, you'd have more sophisticated device fingerprinting
        return {
            "is_anomalous": True,
            "type": "DEVICE_CHANGE",
            "score": 0.4,
            "confidence": 0.5,
            "details": {"device_fingerprint_provided": bool(command.device_fingerprint)},
        }

    def _detect_session_anomaly(self, command: DetectAnomalyCommand, user_id: UUID) -> dict:
        if not command.session_key:
            return {"is_anomalous": False, "type": None, "score": 0.0, "confidence": 0.0}

        # Check session status
        session = self.session_repository.get_by_session_key(command.session_key)

        if session is None:
            return {
                "is_anomalous": True,
                "type": "INVALID_SESSION",
                "score": 0.9,
                "confidence": 1.0,
                "details": {"session_not_found": True},
            }

        if session.state != UserSession.SessionState.ACTIVE:
            return {
                "is_anomalous": True,
                "type": "INACTIVE_SESSION",
                "score": 0.8,
                "confidence": 0.9,
                "details": {"session_state": session.state},
            }

        # Check for concurrent sessions (unusual number)
        active_sessions = self.session_repository.list_by_user(user_id).filter(
            state=UserSession.SessionState.ACTIVE
        ).count()

        if active_sessions > 5:  # Arbitrary threshold
            return {
                "is_anomalous": True,
                "type": "MULTIPLE_SESSIONS",
                "score": 0.6,
                "confidence": 0.7,
                "details": {"active_sessions": active_sessions},
            }

        return {"is_anomalous": False, "type": None, "score": 0.0, "confidence": 0.0}

    def _hash_ip(self, ip_address: str) -> str:
        import hashlib
        return hashlib.sha256(ip_address.encode("utf-8")).hexdigest()
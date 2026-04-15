# Aggregate - Consistency Boundary
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from uuid import UUID

from apps.accounts.domain.entities.session import Session
from apps.accounts.domain.entities.user import User
from apps.accounts.domain.events.authentication_events import (
    DomainEventPublisher,
    SessionCreatedEvent,
    SessionRevokedEvent,
    UserLoggedInEvent,
    UserLoginFailedEvent,
)


@dataclass
class UserAggregate:
    """
    User Aggregate Root.

    Defines the consistency boundary for User and related Sessions.
    All business operations on User and Sessions must go through this aggregate.
    """

    user: User
    sessions: List[Session] = field(default_factory=list)

    def login(self, ip_address: str, user_agent: str) -> Session:
        """
        Business operation: User login.

        Creates a new session and updates user state.
        """
        # Update user for successful login
        updated_user = self.user.record_successful_login()
        self.user = updated_user

        # Create new session
        session = Session(
            user_id=self.user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=f"session_{self.user.id}_{len(self.sessions)}"
        )

        # Add to aggregate
        self.sessions.append(session)

        # Publish domain events
        DomainEventPublisher.publish(UserLoggedInEvent(
            user_id=self.user.id,
            session_id=session.id,
            ip_address=ip_address,
            user_agent=user_agent
        ))

        DomainEventPublisher.publish(SessionCreatedEvent(
            session_id=session.id,
            user_id=self.user.id,
            ip_address=ip_address,
            user_agent=user_agent
        ))

        return session

    def login_failed(self) -> None:
        """
        Business operation: Failed login attempt.

        Updates user state for failed authentication.
        """
        updated_user = self.user.record_failed_login()
        self.user = updated_user

        # Publish domain event
        DomainEventPublisher.publish(UserLoginFailedEvent(
            user_id=self.user.id,
            email=self.user.email.value,
            ip_address="",  # Would be passed in real implementation
            user_agent="",  # Would be passed in real implementation
            failure_reason="INVALID_CREDENTIALS"
        ))

    def revoke_session(self, session_id: UUID, reason: str) -> bool:
        """
        Business operation: Revoke a specific session.

        Ensures session belongs to this user and revokes it.
        """
        for i, session in enumerate(self.sessions):
            if session.id == session_id and session.user_id == self.user.id:
                # Revoke the session
                revoked_session = session.revoke(reason)
                self.sessions[i] = revoked_session

                # Publish domain event
                DomainEventPublisher.publish(SessionRevokedEvent(
                    session_id=session_id,
                    user_id=self.user.id,
                    revoked_reason=reason
                ))

                return True

        return False  # Session not found or doesn't belong to user

    def get_active_sessions(self) -> List[Session]:
        """Query: Get all active sessions for this user."""
        return [session for session in self.sessions if session.is_active()]

    def has_too_many_active_sessions(self, max_sessions: int = 5) -> bool:
        """Business rule: Check if user has too many active sessions."""
        active_count = len(self.get_active_sessions())
        return active_count >= max_sessions

    def revoke_all_sessions(self, reason: str) -> int:
        """
        Business operation: Revoke all sessions for this user.

        Returns number of sessions revoked.
        """
        revoked_count = 0
        for i, session in enumerate(self.sessions):
            if session.is_active():
                revoked_session = session.revoke(reason)
                self.sessions[i] = revoked_session

                DomainEventPublisher.publish(SessionRevokedEvent(
                    session_id=session.id,
                    user_id=self.user.id,
                    revoked_reason=reason
                ))

                revoked_count += 1

        return revoked_count

    def update_session_activity(self, session_id: UUID) -> bool:
        """
        Business operation: Update session last used time.

        Returns True if session was found and updated.
        """
        for i, session in enumerate(self.sessions):
            if session.id == session_id and session.user_id == self.user.id:
                updated_session = session.update_last_used()
                self.sessions[i] = updated_session
                return True

        return False

    # Aggregate invariants (always-true business rules)
    def _check_invariants(self) -> None:
        """Ensure aggregate invariants are maintained."""
        # All sessions must belong to this user
        for session in self.sessions:
            assert session.user_id == self.user.id, "Session must belong to aggregate user"

        # User must be in valid state
        assert self.user.role in [User.Role.PLANNER, User.Role.VENDOR, User.Role.ADMIN], "User must have valid role"
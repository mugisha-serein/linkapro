# Domain Service - Session Policy

class SessionPolicy:
    """
    Domain service for session management policy rules.
    Encapsulates business logic for session creation, validation, and revocation.
    """

    @staticmethod
    def can_create_session(user, device, context) -> bool:
        """Determine if a new session can be created for the user/device."""
        # Example: Limit concurrent sessions
        max_sessions = context.get('max_sessions', 5)
        return context.get('active_sessions', 0) < max_sessions

    @staticmethod
    def is_session_valid(session, context) -> bool:
        """Check if the session is valid according to policy."""
        # Example: Check session state and expiry
        return session.state == 'ACTIVE' and session.expires_at > context['now']

    @staticmethod
    def should_revoke_session(session, context) -> bool:
        """Determine if a session should be revoked."""
        # Example: Revoke if suspicious activity detected
        return context.get('suspicious', False) or session.state == 'SUSPICIOUS'

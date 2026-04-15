# Domain Service - Authentication Policy

class AuthenticationPolicy:
    """
    Domain service for authentication policy rules.
    Encapsulates business logic for login, registration, and credential validation.
    """

    @staticmethod
    def is_login_allowed(user, context) -> bool:
        """Determine if login is allowed for the user in the given context."""
        # Example: Check if user is active and not locked
        return user.is_active and (not user.locked_until or user.locked_until < context['now'])

    @staticmethod
    def is_registration_allowed(email, context) -> bool:
        """Determine if registration is allowed for the given email/context."""
        # Example: Check if email is not blacklisted
        return not context.get('blacklisted_emails', set()).__contains__(email)

    @staticmethod
    def validate_credentials(user, password, context) -> bool:
        """Validate user credentials according to policy."""
        # Example: Check password length and not recently used
        return len(password) >= 8 and password not in context.get('recent_passwords', set())

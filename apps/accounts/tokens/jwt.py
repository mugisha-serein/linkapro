from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from .blacklist import token_revocation_manager

class CustomAccessToken(AccessToken):
    """
    Custom JWT Access Token with additional security claims
    """

    @classmethod
    def for_user(cls, user):
        """
        Create token for user with additional claims
        """
        token = super().for_user(user)

        # Add role claim
        token['role'] = user.role

        # Add device_id if available (for future advanced security)
        # token['device_id'] = device_id  # Optional

        return token


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that checks for token revocation
    """

    def get_validated_token(self, raw_token):
        """
        Validate token and check if it's been revoked
        """
        # First, validate the token using parent class
        token = super().get_validated_token(raw_token)

        # Check if token is revoked by JTI
        jti = token.get('jti')
        if jti and token_revocation_manager.is_token_revoked(jti):
            raise InvalidToken('Token has been revoked')

        # Check if user sessions are revoked
        user_id = token.get('user_id')
        if user_id and token_revocation_manager.is_user_revoked(user_id):
            raise InvalidToken('User sessions have been revoked')

        return token
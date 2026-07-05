import logging

from django_app.identity.cookies import clear_auth_cookies
from django_app.identity.session_revocation import revoke_user_sessions
from django_app.identity.views import ResetPasswordView, SetupPasswordView
from infrastructure.adapters.jwt_token_service import JWTTokenService

logger = logging.getLogger(__name__)


class SessionRevokingSetupPasswordView(SetupPasswordView):
    def post(self, request):
        response = super().post(request)
        if 200 <= response.status_code < 300:
            revoke_user_sessions(request.user.id, reason="password_setup")
            clear_auth_cookies(response)
        return response


class SessionRevokingResetPasswordView(ResetPasswordView):
    def post(self, request):
        user_id = _password_reset_user_id(request)
        response = super().post(request)
        if user_id and 200 <= response.status_code < 300:
            revoke_user_sessions(user_id, reason="password_reset")
            clear_auth_cookies(response)
        return response


def _password_reset_user_id(request):
    token = str(request.data.get("token") or "").strip()
    if not token:
        return None
    payload = JWTTokenService().decode_password_reset_token_payload(token)
    if not payload:
        return None
    return payload.get("user_id")

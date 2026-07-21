import logging

from django_app.identity.cookies import clear_auth_cookies
from django_app.identity.session_revocation import revoke_user_sessions
from django_app.identity.views import ResetPasswordView, SetupPasswordView

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
        response = super().post(request)
        if 200 <= response.status_code < 300:
            clear_auth_cookies(response)
        return response

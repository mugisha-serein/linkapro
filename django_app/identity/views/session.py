from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from django_app.common.api_responses import api_error, api_success
from django_app.identity.services import get_refresh_session_use_case, get_revoke_session_use_case
from django_app.identity.shared.cookies import clear_auth_cookies, extract_refresh_token, set_refresh_cookie
from django_app.identity.shared.csrf_protection import cookie_session_request_is_allowed
from domain.identity.authentication import AuthenticationError
from domain.identity.sessions import SessionError


def _cookie_session_forbidden(request):
    return api_error(
        code="cookie_session_forbidden",
        message="Session request blocked by origin protection.",
        status=status.HTTP_403_FORBIDDEN,
        request=request,
    )


@method_decorator(csrf_exempt, name="dispatch")
class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not cookie_session_request_is_allowed(request):
            return _cookie_session_forbidden(request)

        session_token = extract_refresh_token(request)
        if not session_token:
            response = api_error(
                code="refresh_token_missing",
                message="Authentication required.",
                status=status.HTTP_401_UNAUTHORIZED,
                request=request,
            )
            clear_auth_cookies(response)
            return response

        try:
            access_token, refresh_token, bootstrap_user = get_refresh_session_use_case().execute(session_token)
        except (AuthenticationError, SessionError):
            response = api_error(
                code="refresh_token_invalid",
                message="Authentication required.",
                status=status.HTTP_401_UNAUTHORIZED,
                request=request,
            )
            clear_auth_cookies(response)
            return response

        response = api_success(
            code="token_refreshed",
            message="Session refreshed.",
            data={
                "access": access_token,
                "user": bootstrap_user,
            },
            status=status.HTTP_200_OK,
            request=request,
        )
        set_refresh_cookie(response, refresh_token)
        return response


@method_decorator(csrf_exempt, name="dispatch")
class TokenRevokeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not cookie_session_request_is_allowed(request):
            return _cookie_session_forbidden(request)

        session_token = extract_refresh_token(request)
        if not session_token:
            response = api_success(
                code="session_revoked",
                message="Signed out successfully.",
                data={},
                status=status.HTTP_200_OK,
                request=request,
            )
            clear_auth_cookies(response)
            return response

        try:
            get_revoke_session_use_case().execute(session_token)
        except SessionError:
            response = api_success(
                code="session_revoked",
                message="Signed out successfully.",
                data={},
                status=status.HTTP_200_OK,
                request=request,
            )
            clear_auth_cookies(response)
            return response

        response = api_success(
            code="session_revoked",
            message="Signed out successfully.",
            data={},
            status=status.HTTP_200_OK,
            request=request,
        )
        clear_auth_cookies(response)
        return response

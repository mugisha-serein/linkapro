from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from django_app.common.api_responses import api_error, api_success
from django_app.identity.cookies import clear_auth_cookies, extract_refresh_token, set_refresh_cookie
from django_app.identity.services import get_auth_session_facade


@method_decorator(csrf_exempt, name="dispatch")
class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
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

        session = get_auth_session_facade()
        try:
            result = session.refresh_session(session_token)
        except ValueError:
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
                "access": result.access_token,
                "user": result.bootstrap_user,
            },
            status=status.HTTP_200_OK,
            request=request,
        )
        set_refresh_cookie(response, result.refresh_token)
        return response


@method_decorator(csrf_exempt, name="dispatch")
class TokenRevokeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
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

        session = get_auth_session_facade()
        try:
            session.revoke_session(session_token)
        except ValueError:
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

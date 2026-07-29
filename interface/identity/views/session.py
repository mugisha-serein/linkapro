from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from application.identity.sessions import RevokeOtherSessionsCommand, RevokeSessionCommand
from application.identity.shared.ports import SESSION_ID_CLAIM
from interface.common.api_responses import api_error, api_success
from interface.identity.services import (
    get_list_active_sessions_use_case,
    get_refresh_session_use_case,
    get_revoke_named_session_use_case,
    get_revoke_other_sessions_use_case,
    get_revoke_session_use_case,
)
from interface.identity.shared.cookies import clear_auth_cookies, extract_refresh_token, set_refresh_cookie
from interface.identity.shared.csrf_protection import cookie_session_request_is_allowed
from interface.identity.token_throttles import (
    SessionManagementIPThrottle,
    SessionManagementRateLimited,
    SessionManagementUserThrottle,
)
from domain.identity.authentication import AuthenticationError
from domain.identity.sessions import SessionError


def _cookie_session_forbidden(request):
    return api_error(
        code="cookie_session_forbidden",
        message="Session request blocked by origin protection.",
        status=status.HTTP_403_FORBIDDEN,
        request=request,
    )


def _current_session_id(request) -> str | None:
    token = getattr(request, "auth", None)
    if token is None or not hasattr(token, "get"):
        return None
    session_id = token.get(SESSION_ID_CLAIM)
    return str(session_id) if session_id else None


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


class SessionManagementThrottleMixin:
    permission_classes = [IsAuthenticated]
    throttle_classes = [SessionManagementIPThrottle, SessionManagementUserThrottle]

    def throttled(self, request, wait):
        raise SessionManagementRateLimited(wait=wait, request=request)


class ActiveSessionsView(SessionManagementThrottleMixin, APIView):
    def get(self, request):
        sessions = get_list_active_sessions_use_case().execute(
            user_id=request.user.id,
            current_session_id=_current_session_id(request),
        )
        return api_success(
            code="active_sessions_loaded",
            message="Active sessions loaded.",
            data={"sessions": [session.__dict__ for session in sessions]},
            status=status.HTTP_200_OK,
            request=request,
        )


class RevokeNamedSessionView(SessionManagementThrottleMixin, APIView):
    def post(self, request, session_id):
        result = get_revoke_named_session_use_case().execute(
            RevokeSessionCommand(
                user_id=request.user.id,
                session_id=session_id,
                reason="session_revoked_by_user",
            )
        )
        response = api_success(
            code="session_revoked",
            message="Session revoked.",
            data={"revoked_count": result.revoked_count},
            status=status.HTTP_200_OK,
            request=request,
        )
        if _current_session_id(request) == str(session_id):
            clear_auth_cookies(response)
        return response


class RevokeOtherSessionsView(SessionManagementThrottleMixin, APIView):
    def post(self, request):
        current_session_id = _current_session_id(request)
        if not current_session_id:
            return api_error(
                code="current_session_required",
                message="Current session could not be identified.",
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        result = get_revoke_other_sessions_use_case().execute(
            RevokeOtherSessionsCommand(
                user_id=request.user.id,
                current_session_id=current_session_id,
                reason="other_sessions_revoked_by_user",
            )
        )
        return api_success(
            code="other_sessions_revoked",
            message="Other sessions revoked.",
            data={"revoked_count": result.revoked_count},
            status=status.HTTP_200_OK,
            request=request,
        )

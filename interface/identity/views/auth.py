import logging
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from application.identity.authentication import AuthenticationStatus
from application.identity.account.update_profile_command import UpdateProfileCommand
from application.identity.errors import DuplicateUserError, UserNotFoundError
from application.identity.queries import GetUserByIdQuery
from application.identity.shared.mappers import account_derived_fields
from interface.common.api_responses import api_error, api_success
from interface.identity.services import get_command_handlers, get_query_handlers
from interface.identity.shared.cookies import clear_auth_cookies, set_refresh_cookie
from interface.identity.shared.serializers import LoginSerializer, RegisterSerializer, UpdateProfileSerializer
from interface.identity.throttles import (
    AuthRateLimited,
    LoginEmailThrottle,
    LoginIPThrottle,
    RegisterEmailDomainThrottle,
    RegisterIPThrottle,
    RegistrationRateLimited,
    clear_login_failures,
    get_client_ip,
    rate_limit_hash,
)

logger = logging.getLogger(__name__)


def _auth_error_contract(auth_status):
    mapping = {
        AuthenticationStatus.INVALID_CREDENTIALS: (
            "invalid_credentials",
            "Invalid email or password.",
            {},
        ),
        AuthenticationStatus.INACTIVE: (
            "invalid_credentials",
            "Invalid email or password.",
            {},
        ),
        AuthenticationStatus.SOCIAL_LOGIN_ONLY: (
            "invalid_credentials",
            "Invalid email or password.",
            {},
        ),
        AuthenticationStatus.INVALID_MFA_CODE: (
            "invalid_mfa_code",
            "Invalid verification code.",
            {"token": ["Invalid verification code."]},
        ),
        AuthenticationStatus.INVALID_TEMP_TOKEN: (
            "invalid_mfa_session",
            "Your verification session has expired. Please sign in again.",
            {"temp_token": ["Verification session expired."]},
        ),
        AuthenticationStatus.LOCKED: (
            "account_locked",
            "Too many sign-in attempts. Please try again later.",
            {},
        ),
    }
    return mapping.get(
        auth_status,
        ("authentication_failed", "Authentication failed.", {}),
    )


def _auth_error_response(auth_status, request=None):
    code, message, field_errors = _auth_error_contract(auth_status)
    logger.info("identity_authentication_failed", extra={"auth_status": getattr(auth_status, "value", str(auth_status))})
    response_status = status.HTTP_423_LOCKED if auth_status is AuthenticationStatus.LOCKED else status.HTTP_401_UNAUTHORIZED
    return api_error(
        code=code,
        message=message,
        field_errors=field_errors,
        status=response_status,
        request=request,
    )


def _rate_limited_response(code, message, request=None):
    return api_error(
        code=code,
        message=message,
        field_errors={},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
        request=request,
    )


def _safe_auth_log_metadata(request, *, email=None, temp_token=None, user_id=None):
    normalized_email = str(email or request.data.get("email", "") or "").strip().lower()
    metadata = {
        "request_id": getattr(request, "correlation_id", None),
        "client_ip_hash": rate_limit_hash(get_client_ip(request)),
    }
    if normalized_email:
        metadata["email_hash"] = rate_limit_hash(normalized_email)
        metadata["email_domain"] = normalized_email.rsplit("@", 1)[1] if "@" in normalized_email else ""
    if temp_token:
        metadata["temp_token_hash"] = rate_limit_hash(str(temp_token).strip())
    if user_id:
        metadata["user_id"] = str(user_id)
    return metadata


def _frontend_url() -> str:
    if not settings.FRONTEND_URL:
        raise ValueError("FRONTEND_URL is not configured")
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    if not frontend_url:
        raise ValueError("FRONTEND_URL is not configured")
    if not settings.DEBUG and not frontend_url.lower().startswith("https://"):
        raise ValueError("FRONTEND_URL must use HTTPS in production")
    return frontend_url


def _redirect_error(reason: str):
    params = urlencode({"reason": reason})
    return _no_store_redirect(f"{_frontend_url()}/auth/error?{params}")


def _no_store_redirect(url: str):
    response = redirect(url)
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


def _bootstrap_user_payload(source) -> dict:
    if source is None:
        return {}
    if hasattr(source, "to_dict"):
        return source.to_dict()
    if isinstance(source, dict):
        return source
    role = source.role.value if hasattr(source.role, "value") else source.role
    has_password = getattr(source, "has_password", None)
    if has_password is None:
        has_password = bool(getattr(source, "password_hash", None))
    derived = account_derived_fields(
        first_name=source.first_name,
        last_name=source.last_name,
        email=str(source.email),
        is_verified=source.is_verified,
        has_password=has_password,
    )

    return {
        "id": str(source.id),
        "email": str(source.email),
        "role": role,
        "first_name": source.first_name,
        "last_name": source.last_name,
        "display_name": getattr(source, "display_name", None) or derived["display_name"],
        "avatar": getattr(source, "avatar", None),
        "is_active": source.is_active,
        "is_verified": source.is_verified,
        "has_password": has_password,
        "requires_password_setup": getattr(
            source,
            "requires_password_setup",
            derived["requires_password_setup"],
        ),
        "two_factor_enabled": getattr(source, "two_factor_enabled", False),
        "is_authenticated": True,
        "onboarding_complete": getattr(source, "onboarding_complete", derived["onboarding_complete"]),
    }


def _serialize_user_profile(user_dto) -> dict:
    return _bootstrap_user_payload(user_dto) | {
        "created_at": user_dto.created_at.isoformat() if hasattr(user_dto.created_at, "isoformat") else user_dto.created_at,
        "last_login": (
            user_dto.last_login.isoformat()
            if user_dto.last_login and hasattr(user_dto.last_login, "isoformat")
            else user_dto.last_login
        ),
    }


@method_decorator(csrf_exempt, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterIPThrottle, RegisterEmailDomainThrottle]

    def throttled(self, request, wait):
        raise RegistrationRateLimited(wait=wait, request=request)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="registration_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        cmd = serializer.to_command()
        handlers = get_command_handlers()
        try:
            user_dto = handlers.register_user(cmd)
            logger.info(
                "registration_completed",
                extra=_safe_auth_log_metadata(request, email=serializer.validated_data["email"], user_id=user_dto.id),
            )
            return api_success(
                code="registration_completed",
                message="Account created successfully.",
                data={
                    "user": {
                        "id": str(user_dto.id),
                        "email": user_dto.email,
                        "first_name": user_dto.first_name,
                        "last_name": user_dto.last_name,
                        "role": user_dto.role,
                        "is_verified": getattr(user_dto, "is_verified", False),
                    }
                },
                status=status.HTTP_201_CREATED,
                request=request,
            )
        except DuplicateUserError:
            return api_error(
                code="registration_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors={"email": ["Unable to create an account with these details."]},
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginIPThrottle, LoginEmailThrottle]

    def throttled(self, request, wait):
        raise AuthRateLimited(wait=wait, request=request)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="login_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        email = serializer.validated_data["email"]
        cmd = serializer.to_command()
        auth_result = get_command_handlers().login_user(cmd)
        if auth_result.status is AuthenticationStatus.MFA_REQUIRED:
            clear_login_failures(request, email, user_id=getattr(auth_result.user, "id", None))
            response = api_success(
                code="mfa_required",
                message="Two-factor authentication is required.",
                data={
                    "requires_2fa": True,
                    "temp_token": auth_result.temp_token,
                    "expires_in": 180,
                },
                request=request,
            )
            clear_auth_cookies(response)
            return response

        if auth_result.status is not AuthenticationStatus.AUTHENTICATED:
            response = _auth_error_response(auth_result.status, request=request)
            clear_auth_cookies(response)
            return response

        user = auth_result.user
        clear_login_failures(request, email, user_id=getattr(user, "id", None))
        response = api_success(
            code="login_completed",
            message="Signed in successfully.",
            data={
                "access": auth_result.access_token,
                "token_type": "Bearer",
                "user": auth_result.bootstrap_user or _bootstrap_user_payload(user),
            },
            request=request,
        )
        set_refresh_cookie(response, auth_result.refresh_token)
        return response


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        handlers = get_query_handlers()
        user_dto = handlers.get_user_by_id(GetUserByIdQuery(user_id=request.user.id))
        if not user_dto:
            return api_error(
                code="profile_not_found",
                message="User profile not found.",
                status=status.HTTP_404_NOT_FOUND,
                request=request,
            )

        return api_success(
            code="profile_loaded",
            message="Profile loaded.",
            data={"user": _serialize_user_profile(user_dto)},
            request=request,
        )

    def patch(self, request):
        serializer = UpdateProfileSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return api_error(
                code="profile_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        handlers = get_command_handlers()
        try:
            user_dto = handlers.update_profile(
                UpdateProfileCommand(
                    user_id=request.user.id,
                    first_name=serializer.validated_data.get("first_name"),
                    last_name=serializer.validated_data.get("last_name"),
                )
            )
            return api_success(
                code="profile_updated",
                message="Profile updated successfully.",
                data={"user": _serialize_user_profile(user_dto)},
                request=request,
            )
        except UserNotFoundError:
            return api_error(
                code="profile_update_failed",
                message="Unable to update profile.",
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )

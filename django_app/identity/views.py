import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from application.identity.commands import (
    EnableTwoFactorCommand,
    LoginTwoFactorCommand,
    UpdateProfileCommand,
    VerifyTwoFactorSetupCommand,
)
from application.identity.auth_policy import AuthenticationStatus
from application.identity.oauth_state import (
    ALLOWED_OAUTH_SIGNUP_ROLES,
    OAUTH_STATE_COOKIE_NAME,
    clear_oauth_state_cookie,
    consume_oauth_state,
    issue_oauth_state,
    set_oauth_state_cookie,
)
from application.identity.queries import GetUserByIdQuery
from domain.identity.events import UserPasswordChanged as DomainUserPasswordChanged
from django_app.common.api_responses import api_error, api_success

from .serializers import (
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    SetupPasswordSerializer,
    TwoFactorLoginSerializer,
    TwoFactorSetupVerifySerializer,
    UpdateProfileSerializer,
)
from .services import (
    get_command_handlers,
    get_query_handlers,
    get_google_oauth_adapter,
    get_auth_session_facade,
)
from .cookies import clear_auth_cookies, set_refresh_cookie
from .password_reset_email import GENERIC_FORGOT_PASSWORD_DETAIL, request_password_reset_email
from .throttles import (
    AuthRateLimited,
    ForgotPasswordEmailThrottle,
    ForgotPasswordIPThrottle,
    LoginEmailThrottle,
    LoginIPThrottle,
    LoginUserThrottle,
    PasswordRecoveryRateLimited,
    PasswordResetRateLimited,
    RegisterEmailDomainThrottle,
    RegisterIPThrottle,
    RegistrationRateLimited,
    ResetPasswordIPThrottle,
    ResetPasswordTokenThrottle,
    TwoFactorIPThrottle,
    TwoFactorRateLimited,
    TwoFactorTempTokenThrottle,
    clear_login_failures,
    clear_mfa_failures,
    get_client_ip,
    is_login_locked_out,
    is_mfa_locked_out,
    rate_limit_hash,
    record_login_failure,
    record_mfa_failure,
)
from django_app.identity.models import PasswordResetToken, User
from infrastructure.adapters.django_event_dispatcher import user_password_changed
from infrastructure.adapters.jwt_token_service import JWTTokenService, password_reset_value_hash

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
    }
    return mapping.get(
        auth_status,
        ("authentication_failed", "Authentication failed.", {}),
    )


def _auth_error_response(auth_status, request=None):
    code, message, field_errors = _auth_error_contract(auth_status)
    logger.info("identity_authentication_failed", extra={"auth_status": getattr(auth_status, "value", str(auth_status))})
    return api_error(
        code=code,
        message=message,
        field_errors=field_errors,
        status=status.HTTP_401_UNAUTHORIZED,
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


def _password_reset_invalid_response(field_errors):
    return api_error(
        code="password_reset_validation_failed",
        message="Please fix the highlighted fields.",
        field_errors=field_errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


def _password_reset_token_invalid_response():
    return api_error(
        code="password_reset_token_invalid",
        message="This reset link has expired or is invalid.",
        field_errors={"token": ["Invalid or expired reset token."]},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


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


def _extract_refresh_token(request) -> str | None:
    return request.data.get("refresh") or request.COOKIES.get("refresh_token")


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
    requires_password_setup = getattr(source, "requires_password_setup", None)
    if requires_password_setup is None:
        requires_password_setup = not has_password

    return {
        "id": str(source.id),
        "email": str(source.email),
        "role": role,
        "first_name": source.first_name,
        "last_name": source.last_name,
        "display_name": getattr(source, "display_name", None)
        or f"{source.first_name} {source.last_name}".strip()
        or str(source.email),
        "avatar": getattr(source, "avatar", None),
        "is_active": source.is_active,
        "is_verified": source.is_verified,
        "has_password": has_password,
        "requires_password_setup": requires_password_setup,
        "two_factor_enabled": getattr(source, "two_factor_enabled", False),
        "is_authenticated": True,
        "onboarding_complete": getattr(
            source,
            "onboarding_complete",
            bool(source.is_verified and has_password),
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
        except ValueError:
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
    throttle_classes = [LoginIPThrottle, LoginEmailThrottle, LoginUserThrottle]

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
        if is_login_locked_out(request, email):
            return _rate_limited_response(
                code="login_rate_limited",
                message="Too many sign-in attempts. Please try again later.",
                request=request,
            )
        cmd = serializer.to_command()
        session = get_auth_session_facade()
        auth_result = session.login(cmd)
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
            record_login_failure(request, email, auth_status=auth_result.status)
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


class LoginTwoFactorView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [TwoFactorIPThrottle, TwoFactorTempTokenThrottle]

    def throttled(self, request, wait):
        raise TwoFactorRateLimited(wait=wait, request=request)

    def post(self, request):
        serializer = TwoFactorLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="mfa_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        temp_token = serializer.validated_data["temp_token"]
        if is_mfa_locked_out(request, temp_token):
            return _rate_limited_response(
                code="mfa_rate_limited",
                message="Too many verification attempts. Please try again later.",
                request=request,
            )
        cmd = LoginTwoFactorCommand(
            temp_token=temp_token,
            token=serializer.validated_data["token"],
        )
        session = get_auth_session_facade()
        auth_result = session.login_two_factor(cmd)
        if auth_result.status is not AuthenticationStatus.AUTHENTICATED:
            record_mfa_failure(request, temp_token, auth_status=auth_result.status)
            response = _auth_error_response(auth_result.status, request=request)
            clear_auth_cookies(response)
            return response

        user = auth_result.user
        clear_mfa_failures(request, temp_token, user_id=getattr(user, "id", None))
        response = api_success(
            code="mfa_login_completed",
            message="Signed in successfully.",
            data={
                "access": auth_result.access_token,
                "token_type": "Bearer",
                "user": auth_result.bootstrap_user or _bootstrap_user_payload(user),
            },
            status=status.HTTP_200_OK,
            request=request,
        )
        set_refresh_cookie(response, auth_result.refresh_token)
        return response


@method_decorator(csrf_exempt, name="dispatch")
class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = _extract_refresh_token(request)
        if not refresh_token:
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
            result = session.refresh_session(refresh_token)
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
        refresh_token = _extract_refresh_token(request)
        if not refresh_token:
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
            session.revoke_session(refresh_token)
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


class EnableTwoFactorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cmd = EnableTwoFactorCommand(user_id=request.user.id)
        handlers = get_command_handlers()
        try:
            setup_dto = handlers.enable_two_factor(cmd)
            return api_success(
                code="mfa_setup_started",
                message="Two-factor setup started.",
                data={
                    "secret": setup_dto.secret,
                    "provisioning_uri": setup_dto.provisioning_uri,
                    "qr_code_base64": setup_dto.qr_code_base64,
                },
                request=request,
            )
        except ValueError:
            return api_error(
                code="mfa_setup_failed",
                message="Unable to start two-factor setup.",
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )


class VerifyTwoFactorSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorSetupVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="mfa_setup_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        cmd = VerifyTwoFactorSetupCommand(
            user_id=request.user.id,
            token=serializer.validated_data["token"],
        )
        handlers = get_command_handlers()
        try:
            handlers.verify_two_factor_setup(cmd)
            return api_success(
                code="mfa_enabled",
                message="Two-factor authentication enabled.",
                data={},
                request=request,
            )
        except ValueError:
            return api_error(
                code="mfa_setup_verification_failed",
                message="Invalid verification code.",
                field_errors={"token": ["Invalid verification code."]},
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )


def _serialize_user_profile(user_dto) -> dict:
    return _bootstrap_user_payload(user_dto) | {
        "created_at": user_dto.created_at.isoformat() if hasattr(user_dto.created_at, "isoformat") else user_dto.created_at,
        "last_login": (
            user_dto.last_login.isoformat()
            if user_dto.last_login and hasattr(user_dto.last_login, "isoformat")
            else user_dto.last_login
        ),
    }


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
        except ValueError:
            return api_error(
                code="profile_update_failed",
                message="Unable to update profile.",
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )


class SetupPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SetupPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="password_setup_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        request.user.set_password(serializer.validated_data["password"])
        request.user.save(update_fields=["password", "updated_at"])
        handlers = get_query_handlers()
        user_dto = handlers.get_user_by_id(GetUserByIdQuery(user_id=request.user.id))
        return api_success(
            code="password_setup_completed",
            message="Password set successfully.",
            data={
                "user": _serialize_user_profile(user_dto),
                "role": user_dto.role,
                "next_path": "/dashboard" if user_dto.role == "planner" else f"/{user_dto.role}/dashboard",
                "requires_password_setup": False,
                "vendor_profile": None,
            },
            request=request,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ForgotPasswordIPThrottle, ForgotPasswordEmailThrottle]

    def throttled(self, request, wait):
        raise PasswordRecoveryRateLimited(wait)

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return api_error(
                code="password_recovery_validation_failed",
                message="Please fix the highlighted fields.",
                field_errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        email = serializer.validated_data["email"].strip().lower()
        try:
            request_password_reset_email(email)
        except Exception as exc:
            logger.error(
                "forgot_password_email_dispatch_deferred",
                extra={"email_domain": email.rsplit("@", 1)[-1], "error_type": exc.__class__.__name__},
                exc_info=True,
            )

        return api_success(
            code="password_reset_email_queued",
            message=GENERIC_FORGOT_PASSWORD_DETAIL,
            data={},
            status=status.HTTP_202_ACCEPTED,
            extra={"detail": GENERIC_FORGOT_PASSWORD_DETAIL},
        )


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ResetPasswordIPThrottle, ResetPasswordTokenThrottle]

    def throttled(self, request, wait):
        raise PasswordResetRateLimited(wait)

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            logger.info(
                "reset_password_validation_failed",
                extra={"field_error_keys": list(serializer.errors.keys())},
            )
            return _password_reset_invalid_response(serializer.errors)

        with transaction.atomic():
            verification = JWTTokenService().verify_password_reset_token_once(serializer.validated_data["token"])
            if not verification:
                logger.info("reset_password_invalid_token")
                return _password_reset_token_invalid_response()

            user_id, token_record = verification
            user = User.objects.select_for_update().filter(id=user_id, is_active=True).first()
            if not user:
                logger.info("reset_password_user_missing_or_inactive", extra={"user_id": str(user_id)})
                return _password_reset_token_invalid_response()

            user.set_password(serializer.validated_data["new_password"])
            user.save(update_fields=["password", "updated_at"])
            password_changed_event = DomainUserPasswordChanged(
                user_id=user.id,
                occurred_at=timezone.now(),
                reason="credential_recovery",
            )
            transaction.on_commit(
                lambda event=password_changed_event: user_password_changed.send(
                    sender=self.__class__,
                    event=event,
                )
            )
            token_record.status = PasswordResetToken.Status.USED
            token_record.used_at = timezone.now()
            token_record.used_ip_hash = password_reset_value_hash(_client_ip(request))
            token_record.used_user_agent_hash = password_reset_value_hash(request.META.get("HTTP_USER_AGENT", ""))
            token_record.save(
                update_fields=[
                    "status",
                    "used_at",
                    "used_ip_hash",
                    "used_user_agent_hash",
                    "updated_at",
                ]
            )
            PasswordResetToken.objects.filter(
                user=user,
                status=PasswordResetToken.Status.ACTIVE,
            ).exclude(id=token_record.id).update(status=PasswordResetToken.Status.REVOKED, updated_at=timezone.now())
            logger.info(
                "password_reset_token_consumed",
                extra={"user_id": str(user.id), "jti": token_record.jti},
            )
        return api_success(
            code="password_reset_completed",
            message="Password updated successfully.",
            data={"status": "password_reset"},
            status=status.HTTP_200_OK,
            extra={"status": "password_reset"},
        )


class GoogleLoginView(View):
    def get(self, request):
        signup_role = (request.GET.get("role") or "").strip().lower()
        if signup_role not in ALLOWED_OAUTH_SIGNUP_ROLES:
            return _redirect_error("invalid_role")

        adapter = get_google_oauth_adapter()
        try:
            challenge = issue_oauth_state(signup_role)
            auth_url = adapter.build_auth_url(state=challenge.state)
        except Exception:
            return _redirect_error("oauth_not_configured")
        response = redirect(auth_url)
        set_oauth_state_cookie(response, challenge)
        return response


class GoogleCallbackView(View):
    def get(self, request):
        oauth_error = request.GET.get("error")
        if oauth_error:
            response = _redirect_error(oauth_error)
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            return response

        code = request.GET.get("code")
        if not code:
            response = _redirect_error("missing_code")
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            return response
        frontend_url = _frontend_url()

        state_result = consume_oauth_state(
            request.GET.get("state"),
            request.COOKIES.get(OAUTH_STATE_COOKIE_NAME),
        )
        if not state_result:
            response = _redirect_error("oauth_failed")
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            return response

        adapter = get_google_oauth_adapter()
        try:
            token_data = adapter.exchange_code(code)
            user_data = adapter.get_user_info(token_data["access_token"])
            result = get_auth_session_facade().oauth_login(
                user_data,
                token_data,
                signup_role=state_result.role,
            )
        except Exception:
            response = _redirect_error("oauth_failed")
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            return response

        if result.requires_2fa:
            params = urlencode({"temp_token": result.temp_token or ""})
            response = _no_store_redirect(f"{frontend_url}/auth/2fa?{params}")
            clear_oauth_state_cookie(response)
            clear_auth_cookies(response)
            return response

        response = _no_store_redirect(f"{frontend_url}/auth/success")
        clear_oauth_state_cookie(response)
        if result.refresh:
            set_refresh_cookie(response, result.refresh)
        return response

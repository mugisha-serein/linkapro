from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from application.identity.commands import (
    EnableTwoFactorCommand,
    LoginTwoFactorCommand,
    VerifyTwoFactorSetupCommand,
)
from application.identity.queries import GetUserByIdQuery

from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    TwoFactorLoginSerializer,
    TwoFactorSetupVerifySerializer,
)
from .services import (
    get_command_handlers,
    get_query_handlers,
    get_google_login_use_case,
    get_google_oauth_adapter,
)


def _frontend_url() -> str:
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    if not frontend_url:
        raise ValueError("FRONTEND_URL is not configured")
    if not settings.DEBUG and not frontend_url.lower().startswith("https://"):
        raise ValueError("FRONTEND_URL must use HTTPS in production")
    return frontend_url


def _redirect_error(reason: str):
    params = urlencode({"reason": reason})
    return redirect(f"{_frontend_url()}/auth/error?{params}")


@method_decorator(csrf_exempt, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command()
        handlers = get_command_handlers()
        try:
            user_dto = handlers.register_user(cmd)
            return Response(
                {
                    "id": str(user_dto.id),
                    "email": user_dto.email,
                    "first_name": user_dto.first_name,
                    "last_name": user_dto.last_name,
                    "role": user_dto.role,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command()
        handlers = get_command_handlers()

        domain_user = handlers.user_repo.get_by_email(cmd.email)
        if not domain_user or not handlers.password_hasher.verify(
            cmd.plain_password, domain_user.password_hash
        ):
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not domain_user.is_active:
            return Response(
                {"error": "Account is deactivated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if domain_user.two_factor_enabled:
            temp_token = handlers.token_service.create_temp_token(str(domain_user.id))
            return Response(
                {
                    "requires_2fa": True,
                    "temp_token": temp_token,
                    "expires_in": 180,
                }
            )

        try:
            auth_result = handlers.login_user(cmd)
            return Response(
                {
                    "access_token": auth_result.access_token,
                    "refresh_token": auth_result.refresh_token,
                    "token_type": auth_result.token_type,
                    "user": {
                        "id": str(auth_result.user.id),
                        "email": auth_result.user.email,
                        "first_name": auth_result.user.first_name,
                        "last_name": auth_result.user.last_name,
                        "role": auth_result.user.role,
                    },
                }
            )
        except ValueError as e:
            error_msg = str(e).lower()
            if "invalid credentials" in error_msg or "deactivated" in error_msg:
                return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LoginTwoFactorView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TwoFactorLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = LoginTwoFactorCommand(
            temp_token=serializer.validated_data["temp_token"],
            token=serializer.validated_data["token"],
        )
        handlers = get_command_handlers()
        try:
            auth_result = handlers.login_two_factor(cmd)
            return Response(
                {
                    "access_token": auth_result.access_token,
                    "refresh_token": auth_result.refresh_token,
                    "token_type": auth_result.token_type,
                    "user": {
                        "id": str(auth_result.user.id),
                        "email": auth_result.user.email,
                        "first_name": auth_result.user.first_name,
                        "last_name": auth_result.user.last_name,
                        "role": auth_result.user.role,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class EnableTwoFactorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cmd = EnableTwoFactorCommand(user_id=request.user.id)
        handlers = get_command_handlers()
        try:
            setup_dto = handlers.enable_two_factor(cmd)
            return Response(
                {
                    "secret": setup_dto.secret,
                    "provisioning_uri": setup_dto.provisioning_uri,
                    "qr_code_base64": setup_dto.qr_code_base64,
                }
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyTwoFactorSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorSetupVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = VerifyTwoFactorSetupCommand(
            user_id=request.user.id,
            token=serializer.validated_data["token"],
        )
        handlers = get_command_handlers()
        try:
            handlers.verify_two_factor_setup(cmd)
            return Response({"status": "2FA enabled"})
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        handlers = get_query_handlers()
        user_dto = handlers.get_user_by_id(GetUserByIdQuery(user_id=request.user.id))
        if not user_dto:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "id": str(user_dto.id),
                "email": user_dto.email,
                "first_name": user_dto.first_name,
                "last_name": user_dto.last_name,
                "role": user_dto.role,
                "is_active": user_dto.is_active,
                "is_verified": user_dto.is_verified,
                "created_at": user_dto.created_at,
                "last_login": user_dto.last_login,
            }
        )


class GoogleLoginView(View):
    def get(self, request):
        adapter = get_google_oauth_adapter()
        try:
            auth_url = adapter.build_auth_url()
        except Exception:
            return _redirect_error("oauth_not_configured")
        return redirect(auth_url)


class GoogleCallbackView(View):
    def get(self, request):
        code = request.GET.get("code")
        if not code:
            return _redirect_error("missing_code")
        frontend_url = _frontend_url()

        adapter = get_google_oauth_adapter()
        use_case = get_google_login_use_case()
        try:
            token_data = adapter.exchange_code(code)
            user_data = adapter.get_user_info(token_data["access_token"])
            result = use_case.execute(user_data, token_data)
        except Exception:
            return _redirect_error("oauth_failed")

        if result.requires_2fa:
            params = urlencode({"temp_token": result.temp_token or ""})
            return redirect(f"{frontend_url}/2fa/verify?{params}")

        params = urlencode(
            {
                "access": result.access or "",
                "refresh": result.refresh or "",
            }
        )
        return redirect(f"{frontend_url}/auth/success?{params}")

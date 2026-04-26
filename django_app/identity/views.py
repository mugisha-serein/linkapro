from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from application.identity.commands import EnableTwoFactorCommand, VerifyTwoFactorSetupCommand

from .serializers import RegisterSerializer, LoginSerializer
from .services import get_command_handlers
from application.identity.dtos import AuthenticationResultDTO


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

class LoginTwoFactorView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command()
        handlers = get_command_handlers()
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
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as e:
            # Distinguish between different error types for proper status codes
            error_msg = str(e).lower()
            if "invalid credentials" in error_msg or "account is deactivated" in error_msg:
                return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cmd = serializer.to_command()
        handlers = get_command_handlers()
        try:
            user = handlers.user_repo.get_by_email(cmd.email)   # we need to fetch user first
            if not user or not handlers.password_hasher.verify(cmd.plain_password, user.password_hash):
                raise ValueError("Invalid credentials")

            if user.two_factor_enabled:
                temp_token = handlers.token_service.create_temp_token(str(user.id))
                return Response({
                    "requires_2fa": True,
                    "temp_token": temp_token,
                    "expires_in": 180
                })

            # Normal login flow
            auth_result = handlers.login_user(cmd)
            return Response({ ... })
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        
class EnableTwoFactorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cmd = EnableTwoFactorCommand(user_id=request.user.id)
        handlers = get_command_handlers()
        try:
            setup_dto = handlers.enable_two_factor(cmd)
            return Response({
                "secret": setup_dto.secret,
                "provisioning_uri": setup_dto.provisioning_uri,
                "qr_code_base64": setup_dto.qr_code_base64,
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VerifyTwoFactorSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = serializer.Serializer(data=request.data)
        # add token field
        cmd = VerifyTwoFactorSetupCommand(user_id=request.user.id, token=request.data.get("token"))
        handlers = get_command_handlers()
        try:
            handlers.verify_two_factor_setup(cmd)
            return Response({"status": "2FA enabled"})
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
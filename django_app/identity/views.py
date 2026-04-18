from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

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


class LoginView(APIView):
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
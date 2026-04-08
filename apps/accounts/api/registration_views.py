from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from ..models import User
from .serializers import (
    UserSerializer,
    PlannerRegistrationSerializer,
    VendorRegistrationSerializer,
    AdminCreationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from ..services.password_service import PasswordResetTokenManager
from ..services.rate_limit_service import rate_limiter, get_client_ip
from ..permissions import IsAdminUser


class PlannerRegistrationView(viewsets.ViewSet):
    """
    Register a new Planner user
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        client_ip = get_client_ip(request)
        if not rate_limiter.is_allowed('register', client_ip, limit=5, period_seconds=60):
            return Response(
                {'error': 'Too many registration attempts from this IP. Try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        serializer = PlannerRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    'user': UserSerializer(user).data,
                    'message': 'Planner account created successfully. Please verify your email before logging in.'
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VendorRegistrationView(viewsets.ViewSet):
    """
    Register a new Vendor user
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        client_ip = get_client_ip(request)
        if not rate_limiter.is_allowed('register', client_ip, limit=5, period_seconds=60):
            return Response(
                {'error': 'Too many registration attempts from this IP. Try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        serializer = VendorRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    'user': UserSerializer(user).data,
                    'message': 'Vendor account created successfully. Your profile is in DRAFT status. Please verify your email before logging in.'
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminCreationView(viewsets.ViewSet):
    """
    Create a new Admin user (internal use only)
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['post'], name='create-admin')
    def create_admin(self, request):
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only superusers can create admin accounts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = AdminCreationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    'user': UserSerializer(user).data,
                    'message': 'Admin account created successfully'
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetView(viewsets.ViewSet):
    """
    API endpoints for password reset flow:
    1. Request reset token via email
    2. Confirm reset with token and new password
    """
    permission_classes = [AllowAny]
    token_manager = PasswordResetTokenManager()

    @action(detail=False, methods=['post'], name='request-reset')
    def request_reset(self, request):
        """
        Request a password reset token.
        Sends token to user's email.
        """
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email'].lower()
            if not rate_limiter.is_allowed('password_reset', email, limit=1, period_seconds=3600):
                return Response(
                    {'error': 'Too many password reset requests for this email. Try again later.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            user = User.objects.filter(email=email).first()
            if user:
                # Create reset token and send email only if the account exists
                token = self.token_manager.create_token(user.id, user.email)
                # TODO: Send email with token
                # send_password_reset_email(user.email, token)

            return Response(
                {
                    'message': 'If an account exists for this email, password reset instructions have been sent.'
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], name='confirm-reset')
    def confirm_reset(self, request):
        """
        Confirm password reset with token and new password.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']
            
            # Verify token
            token_data = self.token_manager.verify_token(token)
            if not token_data:
                return Response(
                    {'error': 'Invalid or expired reset token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update password
            try:
                user = User.objects.get(id=token_data['user_id'])
                user.set_password(new_password)
                user.save()
                
                # Invalidate token
                self.token_manager.invalidate_token(token)
                
                return Response(
                    {'message': 'Password reset successfully'},
                    status=status.HTTP_200_OK
                )
            except User.DoesNotExist:
                return Response(
                    {'error': 'Invalid or expired reset token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
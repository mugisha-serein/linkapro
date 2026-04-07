from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from dj_rest_auth.views import LoginView as DRFLoginView

from .models import User
from .serializers import (
    UserSerializer,
    PlannerRegistrationSerializer,
    VendorRegistrationSerializer,
    AdminCreationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from .tokens import RedisTokenManager
from .permissions import (
    IsPlannerUser,
    IsVendorUser,
    IsAdminUser,
    IsApprovedVendor,
)


class PlannerRegistrationView(viewsets.ViewSet):
    """
    Register a new Planner user
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = PlannerRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    'user': UserSerializer(user).data,
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'message': 'Planner account created successfully. Please verify your email.'
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
        serializer = VendorRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    'user': UserSerializer(user).data,
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'message': 'Vendor account created successfully. Your profile is in DRAFT status.'
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminCreationView(viewsets.ViewSet):
    """
    Create a new Admin user (internal use only)
    """
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Only allow superusers to create admins
        if self.action == 'create_admin':
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=['post'], name='create-admin')
    def create_admin(self, request):
        # Check if user is superuser
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


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view that includes user role
    """
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Add user data to response
            email = request.data.get('email')
            user = User.objects.filter(email=email).first()
            if user:
                response.data['user'] = UserSerializer(user).data
        
        return response


class UserDetailView(viewsets.ViewSet):
    """
    Get current user details and update profile
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not user.check_password(old_password):
            return Response(
                {'error': 'Old password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        return Response(
            {'message': 'Password changed successfully'},
            status=status.HTTP_200_OK
        )


class PasswordResetView(viewsets.ViewSet):
    """
    API endpoints for password reset flow:
    1. Request reset token via email
    2. Confirm reset with token and new password
    """
    permission_classes = [AllowAny]
    token_manager = RedisTokenManager()

    @action(detail=False, methods=['post'], name='request-reset')
    def request_reset(self, request):
        """
        Request a password reset token.
        Sends token to user's email (implement in next phase).
        """
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            
            # Create reset token
            token = self.token_manager.create_token(user.id, user.email)
            
            # TODO: Send email with token (next phase)
            # send_password_reset_email(user.email, token)
            
            return Response(
                {
                    'message': 'Password reset link sent to your email',
                    'token': token  # Remove in production - for testing only
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
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

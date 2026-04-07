from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import UserSerializer
from ..tokens import token_revocation_manager
from ..services.rate_limit_service import rate_limiter, get_client_ip
from ..validators.password import validate_password_policy


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view that includes user role and verifies account
    """
    
    def post(self, request, *args, **kwargs):
        # First, authenticate the user to check verification status
        from django.contrib.auth import authenticate
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        client_ip = get_client_ip(request)
        if not rate_limiter.is_allowed('login', client_ip, limit=5, period_seconds=60):
            return Response(
                {'error': 'Too many login attempts from this IP. Try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        user = authenticate(request, email=email, password=password)
        if not user or not getattr(user, 'is_verified', False):
            return Response(
                {'error': 'Invalid credentials or account not verified.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Proceed with token generation
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Add user data to response
            response.data['user'] = UserSerializer(user).data
        
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """
    Refresh token endpoint with per-user rate limiting.
    """

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            user_id = str(token.get('user_id'))
        except Exception:
            return Response(
                {'error': 'Invalid refresh token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not rate_limiter.is_allowed('token_refresh', user_id, limit=10, period_seconds=60):
            return Response(
                {'error': 'Too many token refresh requests. Try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        return super().post(request, *args, **kwargs)


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

        try:
            validate_password_policy(new_password, user=user)
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()
        return Response(
            {'message': 'Password changed successfully'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """
        Logout by revoking the current refresh token
        """
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                # Revoke the refresh token
                token_revocation_manager.revoke_token(
                    jti=token.get('jti'),
                    user_id=request.user.id,
                    expiry_timestamp=token.get('exp')
                )
                return Response(
                    {'message': 'Successfully logged out'},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': 'Refresh token required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def revoke_sessions(self, request):
        """
        Revoke all sessions for the current user
        """
        token_revocation_manager.revoke_user_sessions(request.user.id)
        return Response(
            {'message': 'All sessions revoked. You will need to log in again.'},
            status=status.HTTP_200_OK
        )
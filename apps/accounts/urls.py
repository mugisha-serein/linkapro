from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import (
    PlannerRegistrationView,
    VendorRegistrationView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    UserDetailView,
    PasswordResetView,
)

router = DefaultRouter()
router.register('planner/register', PlannerRegistrationView, basename='planner-register')
router.register('vendor/register', VendorRegistrationView, basename='vendor-register')
router.register('user', UserDetailView, basename='user-detail')
router.register('password-reset', PasswordResetView, basename='password-reset')

app_name = 'accounts'

urlpatterns = [
    # JWT Token Endpoints
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    
    # Registration and User Endpoints
    path('', include(router.urls)),
    
    # dj-rest-auth endpoints (registration and authentication)
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/registration/', include('dj_rest_auth.registration.urls')),
    
    # Django Allauth social login routes
    path('auth/social/', include('allauth.socialaccount.urls')),
]

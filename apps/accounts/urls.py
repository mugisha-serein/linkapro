from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    PlannerRegistrationView,
    VendorRegistrationView,
    AdminCreationView,
    CustomTokenObtainPairView,
    UserDetailView,
    PasswordResetView,
)

router = DefaultRouter()
router.register('planner/register', PlannerRegistrationView, basename='planner-register')
router.register('vendor/register', VendorRegistrationView, basename='vendor-register')
router.register('admin/create', AdminCreationView, basename='admin-create')
router.register('user', UserDetailView, basename='user-detail')
router.register('password-reset', PasswordResetView, basename='password-reset')

app_name = 'accounts'

urlpatterns = [
    # JWT Token Endpoints
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Registration and User Endpoints
    path('', include(router.urls)),
    
    # dj-rest-auth endpoints (includes social auth)
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/registration/', include('dj_rest_auth.registration.urls')),
    path('auth/social/', include('allauth.socialaccount.urls')),
]

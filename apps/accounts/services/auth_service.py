from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied


def authenticate_user(email, password, request=None):
    user = authenticate(request=request, email=email, password=password)
    if user is None:
        return None

    if not getattr(user, 'is_verified', False):
        raise PermissionDenied('Account not verified')

    return user

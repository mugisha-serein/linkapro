from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.views import exception_handler

from interface.common.api_responses import api_error_payload


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    request = context.get("request") if context else None
    if isinstance(exc, NotAuthenticated):
        response.data = api_error_payload(
            code="authentication_required",
            message=str(exc.detail),
            request=request,
        )
        response.status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, PermissionDenied):
        response.data = api_error_payload(
            code="permission_denied",
            message=str(exc.detail),
            request=request,
        )
        response.status_code = status.HTTP_403_FORBIDDEN
    return response

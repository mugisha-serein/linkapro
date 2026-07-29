from rest_framework.response import Response


def api_success(code, message, data=None, status=200, extra=None, request=None):
    payload = {
        "success": True,
        "code": code,
        "message": message,
        "data": data or {},
    }
    if extra:
        payload.update(extra)
    request_id = getattr(request, "correlation_id", None) if request is not None else None
    if request_id:
        payload["request_id"] = request_id
    return Response(payload, status=status)


def api_error(code, message, field_errors=None, status=400, extra=None, request=None):
    return Response(
        api_error_payload(
            code=code,
            message=message,
            field_errors=field_errors,
            extra=extra,
            request=request,
        ),
        status=status,
    )


def api_error_payload(code, message, field_errors=None, extra=None, request=None):
    payload = {
        "success": False,
        "code": code,
        "message": message,
        "field_errors": field_errors or {},
    }
    if extra:
        payload.update(extra)
    request_id = getattr(request, "correlation_id", None) if request is not None else None
    if request_id:
        payload["request_id"] = request_id
    return payload

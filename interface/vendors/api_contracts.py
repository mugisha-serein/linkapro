from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from application.vendors.errors import (
    InvalidVendorCommand,
    VendorApplicationError,
    VendorConflict,
    VendorOperationForbidden,
    VendorResourceNotFound,
)
from domain.vendors.shared.aggregate import ConcurrentVendorUpdate, VendorDomainError


EXPECTED_VERSION_CODE = "vendor_expected_version_invalid"


def _parse_version_value(value, field_name: str) -> tuple[int | None, dict[str, list[str]]]:
    if isinstance(value, bool) or value is None:
        return None, {field_name: ["Must be a nonnegative integer."]}
    if isinstance(value, int):
        version = value
    elif isinstance(value, str):
        raw = value.strip()
        if raw.startswith("W/"):
            raw = raw[2:].strip()
        raw = raw.strip('"')
        if not raw.isdigit():
            return None, {field_name: ["Must be a nonnegative integer."]}
        version = int(raw)
    else:
        return None, {field_name: ["Must be a nonnegative integer."]}
    if version < 0:
        return None, {field_name: ["Must be a nonnegative integer."]}
    return version, {}


def resolve_expected_version(request) -> tuple[int | None, Response | None]:
    header = request.headers.get("If-Match")
    body_supplied = isinstance(request.data, dict) and "expected_version" in request.data

    header_version = None
    body_version = None
    field_errors: dict[str, list[str]] = {}

    if header is not None and header.strip():
        header_version, errors = _parse_version_value(header, "If-Match")
        field_errors.update(errors)
    if body_supplied:
        body_version, errors = _parse_version_value(request.data.get("expected_version"), "expected_version")
        field_errors.update(errors)

    if field_errors:
        return None, vendor_error_response(
            code=EXPECTED_VERSION_CODE,
            message="Expected resource version is invalid.",
            field_errors=field_errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if header_version is None and body_version is None:
        return None, vendor_error_response(
            code="vendor_expected_version_required",
            message="Expected resource version is required.",
            field_errors={"expected_version": ["Send If-Match or expected_version."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if header_version is not None and body_version is not None and header_version != body_version:
        return None, vendor_error_response(
            code="vendor_expected_version_conflict",
            message="Expected version values do not match.",
            field_errors={"expected_version": ["If-Match and expected_version must match."]},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return (header_version if header_version is not None else body_version), None


def vendor_error_response(
    *,
    code: str,
    message: str,
    field_errors: dict[str, list[str]] | None = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    detail: str | None = None,
) -> Response:
    return Response(
        {
            "code": code,
            "message": message,
            "detail": detail or message,
            "field_errors": field_errors or {},
        },
        status=status_code,
    )


def response_with_version(response: Response, version: int | None) -> Response:
    if version is None:
        return response
    response["ETag"] = f'"{version}"'
    response["X-Resource-Version"] = str(version)
    return response


def map_vendor_exception(exc: Exception) -> Response | None:
    if isinstance(exc, VendorResourceNotFound):
        return vendor_error_response(
            code=exc.code,
            message=exc.message,
            field_errors=exc.field_errors,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if isinstance(exc, VendorConflict):
        return vendor_error_response(
            code=exc.code,
            message=exc.message,
            field_errors=exc.field_errors,
            status_code=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, VendorOperationForbidden):
        return vendor_error_response(
            code=exc.code,
            message=exc.message,
            field_errors=exc.field_errors,
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, InvalidVendorCommand):
        return vendor_error_response(
            code=exc.code,
            message=exc.message,
            field_errors=exc.field_errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, VendorApplicationError):
        return vendor_error_response(
            code=exc.code,
            message=exc.message,
            field_errors=exc.field_errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, ConcurrentVendorUpdate):
        return vendor_error_response(
            code=exc.code,
            message=str(exc),
            field_errors=exc.field_errors,
            status_code=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, VendorDomainError):
        return vendor_error_response(
            code=exc.code,
            message=str(exc),
            field_errors=exc.field_errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return None

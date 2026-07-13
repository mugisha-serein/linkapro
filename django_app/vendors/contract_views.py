from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from application.vendors.commands import DeactivateServicePackageCommand, UpdateServicePackageCommand
from .api_contracts import map_vendor_exception, resolve_expected_version, response_with_version, vendor_error_response
from domain.vendors.package_edit_policy import (
    PackageEditCooldownError,
    VENDOR_PACKAGE_EDIT_COOLDOWN_DAYS,
    effective_next_edit_allowed_at,
)
from domain.vendors.package_rules import PackageValidationError
from domain.vendors.errors import ConcurrentVendorUpdate, VendorDomainError

from .document_upload_views import VendorVerificationDocumentView as BaseVendorVerificationDocumentView
from .models import ServicePackage as ServicePackageModel
from .serializers import ServicePackageSerializer
from .services import get_command_handlers
from .package_views import (
    ServicePackageActivateView as BaseServicePackageActivateView,
    ServicePackageDetailView as BaseServicePackageDetailView,
    ServicePackageListView as BaseServicePackageListView,
)
from .portfolio_views import PortfolioImageView as BasePortfolioImageView
from .profile_views import VendorProfileStatusView as BaseVendorProfileStatusView
from .vendor_view_common import (
    _get_current_vendor_profile,
    _stable_package_integrity_response,
)


PACKAGE_NOT_FOUND_MESSAGE = "Package not found or does not belong to this vendor."


def _message_from_response(response: Response, fallback: str) -> str:
    data = response.data if isinstance(response.data, dict) else {}
    return str(data.get("message") or data.get("detail") or fallback)


def _add_success_contract(response: Response, *, code: str, message: str) -> Response:
    if isinstance(response.data, dict):
        response.data.setdefault("success", True)
        response.data.setdefault("code", code)
        response.data.setdefault("message", message)
    return response


def _add_error_contract(response: Response, *, code: str, message: str) -> Response:
    if not isinstance(response.data, dict):
        return response

    field_errors = response.data.get("field_errors")
    if field_errors is None:
        field_errors = {
            key: value
            for key, value in response.data.items()
            if isinstance(value, list)
        }

    response.data.setdefault("success", False)
    response.data.setdefault("code", code)
    response.data.setdefault("message", _message_from_response(response, message))
    response.data.setdefault("detail", response.data["message"])
    response.data.setdefault("field_errors", field_errors or {})
    return response


def _normalize_response_contract(
    response: Response,
    *,
    success_code: str,
    success_message: str,
    error_code: str,
    error_message: str,
) -> Response:
    if response.status_code >= status.HTTP_400_BAD_REQUEST:
        return _add_error_contract(response, code=error_code, message=error_message)
    return _add_success_contract(response, code=success_code, message=success_message)


def _serialize_dt(value):
    return value.isoformat() if value else None


def _package_cooldown_contract(package: ServicePackageModel) -> dict:
    next_allowed = effective_next_edit_allowed_at(package)
    now = timezone.now()
    return {
        "last_approved_at": _serialize_dt(package.last_approved_at),
        "last_vendor_public_edit_at": _serialize_dt(package.last_vendor_public_edit_at),
        "next_vendor_edit_allowed_at": _serialize_dt(next_allowed),
        "can_edit_now": next_allowed is None or now >= next_allowed,
        "package_edit_cooldown_days": VENDOR_PACKAGE_EDIT_COOLDOWN_DAYS,
    }


def _augment_package_payload(payload):
    if not isinstance(payload, dict) or not payload.get("id"):
        return payload
    try:
        package = ServicePackageModel.all_objects.get(id=payload["id"])
    except ServicePackageModel.DoesNotExist:
        return payload
    payload.update(_package_cooldown_contract(package))
    return payload


def _augment_package_response(response: Response) -> Response:
    if isinstance(response.data, list):
        for payload in response.data:
            _augment_package_payload(payload)
    elif isinstance(response.data, dict):
        if isinstance(response.data.get("results"), list):
            for payload in response.data["results"]:
                _augment_package_payload(payload)
        _augment_package_payload(response.data)
        if isinstance(response.data.get("package"), dict):
            _augment_package_payload(response.data["package"])
    return response


class VendorProfileStatusView(BaseVendorProfileStatusView):
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        response = super().get(request)
        return _add_success_contract(
            response,
            code="vendor_profile_status_loaded",
            message="Vendor profile status loaded.",
        )


class PortfolioImageView(BasePortfolioImageView):
    def delete(self, request, image_id):
        response = super().delete(request, image_id)
        return _normalize_response_contract(
            response,
            success_code="vendor_portfolio_item_removed",
            success_message="Portfolio item removed from active listings.",
            error_code="vendor_portfolio_item_not_found",
            error_message="Portfolio item not found or does not belong to this vendor.",
        )


class ServicePackageListView(BaseServicePackageListView):
    def get(self, request):
        return _augment_package_response(super().get(request))

    def post(self, request):
        return _augment_package_response(super().post(request))


class ServicePackageDetailView(BaseServicePackageDetailView):
    def patch(self, request, package_id):
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response

        serializer = ServicePackageSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        expected_version, version_error = resolve_expected_version(request)
        if version_error:
            return version_error
        cmd = UpdateServicePackageCommand(
            package_id=package_id,
            vendor_id=profile.id,
            expected_version=expected_version,
            name=data.get("name"),
            description=data.get("description"),
            price=data.get("price"),
            currency=data.get("currency"),
            package_tier=data.get("package_tier"),
        )

        try:
            updated = get_command_handlers().update_service_package(cmd)
            response = response_with_version(Response(BaseServicePackageListView._serialize_package(None, updated)), updated.version)
        except PackageEditCooldownError as exc:
            response = vendor_error_response(
                code=exc.code,
                message=exc.message,
                detail=exc.message,
                field_errors={
                    "next_vendor_edit_allowed_at": [
                        exc.next_allowed_at.isoformat(),
                    ]
                },
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except ConcurrentVendorUpdate as exc:
            response = _stable_package_integrity_response(exc)
        except PackageValidationError as exc:
            raise DRFValidationError(exc.errors)
        except (IntegrityError, VendorDomainError) as exc:
            response = _stable_package_integrity_response(exc, status_code=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            response = map_vendor_exception(exc)
            if response is None:
                raise
        response = _augment_package_response(response)
        return _normalize_response_contract(
            response,
            success_code="vendor_package_updated",
            success_message="Service package updated.",
            error_code="vendor_package_not_found",
            error_message=PACKAGE_NOT_FOUND_MESSAGE,
        )

    def delete(self, request, package_id):
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        expected_version, version_error = resolve_expected_version(request)
        if version_error:
            return version_error

        cmd = DeactivateServicePackageCommand(
            package_id=package_id,
            vendor_id=profile.id,
            expected_version=expected_version,
            deleted_by_id=request.user.id,
        )
        try:
            package = get_command_handlers().deactivate_package(cmd)
            response = Response(
                {
                    "message": "Package removed from active listings.",
                    "package": BaseServicePackageListView._serialize_package(None, package),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            response = map_vendor_exception(exc)
            if response is None:
                raise
        response = _augment_package_response(response)
        return _normalize_response_contract(
            response,
            success_code="vendor_package_removed",
            success_message="Package removed from active listings.",
            error_code="vendor_package_not_found",
            error_message=PACKAGE_NOT_FOUND_MESSAGE,
        )


class ServicePackageActivateView(BaseServicePackageActivateView):
    def post(self, request, package_id):
        response = super().post(request, package_id)
        return _add_error_contract(
            response,
            code="vendor_package_admin_approval_required",
            message="Package publication requires admin approval.",
        )


class VendorVerificationDocumentView(BaseVendorVerificationDocumentView):
    def post(self, request):
        response = super().post(request)
        return _normalize_response_contract(
            response,
            success_code="vendor_verification_document_queued",
            success_message="Document received. Verification will continue automatically.",
            error_code="vendor_verification_document_invalid",
            error_message="Upload a valid verification PDF.",
        )

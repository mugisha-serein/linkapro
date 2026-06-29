from rest_framework import status
from rest_framework.response import Response

from .document_upload_views import VendorVerificationDocumentView as BaseVendorVerificationDocumentView
from .views import (
    PortfolioImageView as BasePortfolioImageView,
    ServicePackageActivateView as BaseServicePackageActivateView,
    ServicePackageDetailView as BaseServicePackageDetailView,
    VendorProfileStatusView as BaseVendorProfileStatusView,
)


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


class VendorProfileStatusView(BaseVendorProfileStatusView):
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


class ServicePackageDetailView(BaseServicePackageDetailView):
    def patch(self, request, package_id):
        response = super().patch(request, package_id)
        return _normalize_response_contract(
            response,
            success_code="vendor_package_updated",
            success_message="Service package updated.",
            error_code="vendor_package_not_found",
            error_message="Package not found or does not belong to this vendor.",
        )

    def delete(self, request, package_id):
        response = super().delete(request, package_id)
        return _normalize_response_contract(
            response,
            success_code="vendor_package_removed",
            success_message="Package removed from active listings.",
            error_code="vendor_package_not_found",
            error_message="Package not found or does not belong to this vendor.",
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

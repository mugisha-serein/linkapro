from __future__ import annotations

from ..vendor_view_common import *
from ..vendor_view_common import _get_current_vendor_profile
from ..vendor_view_common import _page_request_from_query
from ..vendor_view_common import _actor
from ..vendor_view_common import _stable_package_integrity_response
from ..vendor_view_common import _add_error_contract
from ..vendor_view_common import _normalize_response_contract
from django.utils import timezone
from domain.vendors.packages.rules import PackageEditCooldownError, VENDOR_PACKAGE_EDIT_COOLDOWN_DAYS, effective_next_edit_allowed_at


PACKAGE_NOT_FOUND_MESSAGE = "Package not found or does not belong to this vendor."


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


def _package_not_found_response() -> Response:
    return _normalize_response_contract(
        vendor_error_response(
            code="vendor_package_not_found",
            message=PACKAGE_NOT_FOUND_MESSAGE,
            status_code=status.HTTP_404_NOT_FOUND,
        ),
        success_code="vendor_package_updated",
        success_message="Service package updated.",
        error_code="vendor_package_not_found",
        error_message=PACKAGE_NOT_FOUND_MESSAGE,
    )


def _resolve_package_expected_version(request, package: ServicePackageModel):
    expected_version, version_error = resolve_expected_version(request)
    if version_error is None:
        return expected_version, None
    if isinstance(version_error.data, dict) and version_error.data.get("code") == "vendor_expected_version_required":
        return package.version, None
    return None, version_error


class ServicePackageListView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """List service packages for the current vendor."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()
        page_request, pagination_error = _page_request_from_query(request)
        if pagination_error:
            return pagination_error

        query = ListServicePackagesQuery(
            actor=_actor(request),
            vendor_id=profile.id,
            page=page_request,
            search_text=request.query_params.get("q"),
        )
        page = query_handlers.list_service_packages(query)
        next_offset = page.offset + page.limit if page.offset + page.limit < page.total else None
        response = Response(
            {
                "count": page.total,
                "limit": page.limit,
                "offset": page.offset,
                "next_offset": next_offset,
                "results": [self._serialize_package(pkg) for pkg in page.items],
            }
        )
        return _augment_package_response(response)

    def post(self, request):
        """Create a new service package."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response

        serializer = ServicePackageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cmd = CreateServicePackageCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            name=data["name"],
            description=data["description"],
            price=data["price"],
            currency=data.get("currency", "RWF"),
            package_tier=data["package_tier"],
            idempotency_key=request.headers.get("Idempotency-Key") or str(uuid.uuid4()),
        )

        command_handlers = get_command_handlers()
        try:
            package = command_handlers.create_service_package(cmd)
        except PackageValidationError as exc:
            raise DRFValidationError(exc.errors)
        except IntegrityError as exc:
            return _stable_package_integrity_response(exc)
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise
        return response_with_version(_augment_package_response(Response(self._serialize_package(package), status=status.HTTP_201_CREATED)), package.version)

    def _serialize_package(self, dto: ServicePackageDTO) -> dict:
        return {
            "id": str(dto.id),
            "name": dto.name,
            "description": dto.description,
            "price": str(dto.price),
            "currency": dto.currency,
            "package_tier": dto.package_tier,
            "approval_status": dto.approval_status,
            "rejection_reason": dto.rejection_reason,
            "is_active": dto.is_active,
            "is_deleted": dto.is_deleted,
            "deleted_at": dto.deleted_at.isoformat() if dto.deleted_at else None,
            "version": dto.version,
        }


class ServicePackageDetailView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def patch(self, request, package_id):
        """Update a service package."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        package = ServicePackageModel.all_objects.filter(id=package_id, vendor_id=profile.id).first()
        if package is None:
            return _package_not_found_response()

        serializer = ServicePackageSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        expected_version, version_error = _resolve_package_expected_version(request, package)
        if version_error:
            return _normalize_response_contract(
                version_error,
                success_code="vendor_package_updated",
                success_message="Service package updated.",
                error_code="vendor_package_not_found",
                error_message=PACKAGE_NOT_FOUND_MESSAGE,
            )

        cmd = UpdateServicePackageCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            package_id=package_id,
            expected_version=expected_version,
            name=data.get("name"),
            description=data.get("description"),
            price=data.get("price"),
            currency=data.get("currency"),
            package_tier=data.get("package_tier"),
        )

        command_handlers = get_command_handlers()
        try:
            updated = command_handlers.update_service_package(cmd)
            response = response_with_version(Response(ServicePackageListView._serialize_package(None, updated)), updated.version)
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
        except PackageValidationError as exc:
            raise DRFValidationError(exc.errors)
        except ConcurrentVendorUpdate as exc:
            response = _stable_package_integrity_response(exc)
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
        """Deactivate a service package (soft delete)."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        package_model = ServicePackageModel.all_objects.filter(id=package_id, vendor_id=profile.id).first()
        if package_model is None:
            return _normalize_response_contract(
                vendor_error_response(
                    code="vendor_package_not_found",
                    message=PACKAGE_NOT_FOUND_MESSAGE,
                    status_code=status.HTTP_404_NOT_FOUND,
                ),
                success_code="vendor_package_removed",
                success_message="Package removed from active listings.",
                error_code="vendor_package_not_found",
                error_message=PACKAGE_NOT_FOUND_MESSAGE,
            )

        expected_version, version_error = _resolve_package_expected_version(request, package_model)
        if version_error:
            return _normalize_response_contract(
                version_error,
                success_code="vendor_package_removed",
                success_message="Package removed from active listings.",
                error_code="vendor_package_not_found",
                error_message=PACKAGE_NOT_FOUND_MESSAGE,
            )

        cmd = DeactivateServicePackageCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            package_id=package_id,
            expected_version=expected_version,
        )
        command_handlers = get_command_handlers()
        try:
            package = command_handlers.deactivate_package(cmd)
            response = Response(
                {
                    "message": "Package removed from active listings.",
                    "package": ServicePackageListView._serialize_package(None, package),
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


class ServicePackageActivateView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request, package_id):
        """Vendor packages must be approved by an administrator before publication."""
        _, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return _add_error_contract(
                error_response,
                code="vendor_package_admin_approval_required",
                message="Package publication requires admin approval.",
            )
        response = Response(
            {"detail": "Package publication requires admin approval."},
            status=status.HTTP_403_FORBIDDEN,
        )
        return _add_error_contract(
            response,
            code="vendor_package_admin_approval_required",
            message="Package publication requires admin approval.",
        )

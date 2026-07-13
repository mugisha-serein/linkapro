from __future__ import annotations

from .vendor_view_common import *


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

        query = ListServicePackagesQuery(actor=_actor(request), vendor_id=profile.id, page=page_request)
        page = query_handlers.list_service_packages(query)
        next_offset = page.offset + page.limit if page.offset + page.limit < page.total else None
        return Response(
            {
                "count": page.total,
                "limit": page.limit,
                "offset": page.offset,
                "next_offset": next_offset,
                "results": [self._serialize_package(pkg) for pkg in page.items],
            }
        )

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
        return response_with_version(Response(self._serialize_package(package), status=status.HTTP_201_CREATED), package.version)

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
        query_handlers = get_query_handlers()

        # Verify ownership
        query = ListServicePackagesQuery(actor=_actor(request), vendor_id=profile.id)
        packages = query_handlers.list_service_packages(query)
        pkg = next((p for p in packages.items if p.id == package_id), None)
        if not pkg:
            return Response(
                {"detail": "Package not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ServicePackageSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        expected_version, version_error = resolve_expected_version(request)
        if version_error:
            return version_error

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
        except PackageValidationError as exc:
            raise DRFValidationError(exc.errors)
        except ConcurrentVendorUpdate as exc:
            return _stable_package_integrity_response(exc)
        except (IntegrityError, VendorDomainError) as exc:
            return _stable_package_integrity_response(exc, status_code=status.HTTP_400_BAD_REQUEST)
        return response_with_version(Response(ServicePackageListView._serialize_package(None, updated)), updated.version)

    def delete(self, request, package_id):
        """Deactivate a service package (soft delete)."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        query = ListServicePackagesQuery(actor=_actor(request), vendor_id=profile.id)
        packages = query_handlers.list_service_packages(query)
        pkg = next((p for p in packages.items if p.id == package_id), None)
        if not pkg:
            return Response(
                {"detail": "Package not found or does not belong to this vendor."},
                status=status.HTTP_404_NOT_FOUND
            )

        expected_version, version_error = resolve_expected_version(request)
        if version_error:
            return version_error

        cmd = DeactivateServicePackageCommand(
            actor=_actor(request),
            vendor_id=profile.id,
            package_id=package_id,
            expected_version=expected_version,
        )
        command_handlers = get_command_handlers()
        try:
            package = command_handlers.deactivate_package(cmd)
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise
        return Response(
            {
                "message": "Package removed from active listings.",
                "package": ServicePackageListView._serialize_package(None, package),
            },
            status=status.HTTP_200_OK,
        )


class ServicePackageActivateView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request, package_id):
        """Vendor packages must be approved by an administrator before publication."""
        _, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        return Response(
            {"detail": "Package publication requires admin approval."},
            status=status.HTTP_403_FORBIDDEN,
        )

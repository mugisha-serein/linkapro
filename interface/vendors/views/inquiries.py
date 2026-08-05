from __future__ import annotations

import logging

from ..vendor_view_common import *
from ..vendor_view_common import _get_current_vendor_profile
from ..vendor_view_common import _actor

logger = logging.getLogger(__name__)


class InquiryListView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        """List inquiries for the current vendor."""
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        query_handlers = get_query_handlers()

        query = ListInquiriesQuery(
            actor=_actor(request),
            vendor_id=profile.id,
            search_text=request.query_params.get("q"),
        )
        inquiries = query_handlers.list_inquiries(query)
        return Response([self._serialize_inquiry(inq) for inq in inquiries.items])

    def _serialize_inquiry(self, dto: InquiryDTO) -> dict:
        return {
            "id": str(dto.id),
            "client_name": dto.client_name,
            "client_email": dto.client_email,
            "client_phone": dto.client_phone,
            "message": dto.message,
            "event_date": dto.event_date.isoformat() if dto.event_date else None,
            "is_read": dto.is_read,
            "created_at": dto.created_at.isoformat(),
            "version": dto.version,
        }


class PublicInquiryView(APIView):
    """Endpoint for authenticated clients to send inquiries to a vendor."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PublicVendorInquiryThrottle]
    throttle_scope = "public_vendor_inquiry"
    deprecated_route_name: str | None = None

    def post(self, request, vendor_id):
        if not VendorProfileModel.objects.filter(
            id=vendor_id,
            status=VendorProfileModel.Status.APPROVED,
        ).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = InquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        actor = _actor(request)
        sender_name = _request_user_display_name(request.user)

        # Snapshot authenticated contact details at submit time. Authorization
        # and requester identity are tied only to actor.user_id.
        cmd = SendInquiryCommand(
            actor=actor,
            vendor_id=uuid.UUID(str(vendor_id)),
            client_name=sender_name,
            client_email=request.user.email,
            message=data["message"],
            client_phone=data.get("client_phone"),
            event_date=data.get("event_date"),
            idempotency_key=request.headers.get("Idempotency-Key") or str(uuid.uuid4()),
        )

        command_handlers = get_command_handlers()
        try:
            inquiry = command_handlers.send_inquiry(cmd)
            return api_success(
                code="vendor_inquiry_created",
                message="Inquiry sent successfully.",
                data={"id": str(inquiry.id)},
                status=status.HTTP_201_CREATED,
                request=request,
            )
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if not self.deprecated_route_name:
            return response
        vendor_id = getattr(self, "kwargs", {}).get("vendor_id")
        logger.warning(
            "deprecated_public_vendor_inquiry_route_hit",
            extra={
                "route_name": self.deprecated_route_name,
                "path": request.path,
                "vendor_id": str(vendor_id),
            },
        )
        response["Deprecation"] = "true"
        response["Link"] = f'<{request.build_absolute_uri("../inquiry/")}>; rel="successor-version"'
        response["X-Deprecated-Route"] = self.deprecated_route_name
        return response


def _request_user_display_name(user) -> str:
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = get_full_name()
        if full_name:
            return full_name
    return f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or user.email

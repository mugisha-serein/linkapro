from __future__ import annotations

from ..vendor_view_common import *
from ..vendor_view_common import _get_current_vendor_profile
from ..vendor_view_common import _actor


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
    """Public endpoint for clients to send inquiries to a vendor (no auth required)."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicVendorInquiryThrottle]
    throttle_scope = "public_vendor_inquiry"

    def post(self, request, vendor_id):
        if not VendorProfileModel.objects.filter(
            id=vendor_id,
            status=VendorProfileModel.Status.APPROVED,
        ).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = InquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cmd = SendInquiryCommand(
            vendor_id=uuid.UUID(str(vendor_id)),
            requester_id=_public_inquiry_requester_id(data["client_email"]),
            client_name=data["client_name"],
            client_email=data["client_email"],
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


def _public_inquiry_requester_id(client_email: str) -> uuid.UUID:
    normalized = str(client_email).strip().lower()
    return uuid.uuid5(uuid.NAMESPACE_URL, f"linkapro:public-inquiry:{normalized}")

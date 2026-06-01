from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django_app.common.permissions import IsAdmin
from django_app.identity.models import User
from django_app.events.models import Event
from django_app.vendors.models import VendorProfile
from .serializers import FlagContentSerializer
from .services import get_command_handlers, get_query_handlers
from application.governance.commands import FlagContentCommand


class FlagContentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FlagContentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cmd = FlagContentCommand(
            reported_by=request.user.id,
            content_type=serializer.validated_data["content_type"],
            content_id=serializer.validated_data["content_id"],
            reason=serializer.validated_data["reason"],
        )

        handlers = get_command_handlers()
        flag_dto = handlers.flag_content(cmd)

        return Response({
            "id": str(flag_dto.id),
            "status": flag_dto.status,
            "message": "Content flagged successfully. Our team will review it."
        }, status=status.HTTP_201_CREATED)


class AdminMetricsView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        query_handlers = get_query_handlers()
        latest = query_handlers.get_latest_metrics()

        if latest:
            return Response(
                {
                    "total_users": latest.total_users,
                    "active_vendors": latest.active_vendors,
                    "payments_today": 0,
                    "fraud_signals": 0,
                    "total_events": latest.total_events,
                    "total_vendors": latest.total_vendors,
                    "revenue": "0",
                    "pending_vendor_approvals": latest.pending_vendor_approvals,
                }
            )

        return Response(
            {
                "total_users": User.objects.count(),
                "active_vendors": VendorProfile.objects.filter(status=VendorProfile.Status.APPROVED).count(),
                "payments_today": 0,
                "fraud_signals": 0,
                "total_events": Event.objects.count(),
                "total_vendors": VendorProfile.objects.count(),
                "revenue": "0",
                "pending_vendor_approvals": VendorProfile.objects.filter(
                    status=VendorProfile.Status.PENDING_REVIEW
                ).count(),
            }
        )
from __future__ import annotations

from ..vendor_view_common import *


class AdminPendingVendorListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from django_app.vendors.models import VendorProfile

        pending = VendorProfile.objects.filter(status=VendorProfile.Status.PENDING_REVIEW).select_related("user")
        return Response([
            {
                "id": str(profile.id),
                "user_id": str(profile.user_id),
                "business_name": profile.business_name,
                "category": profile.category,
                "custom_category": profile.custom_category,
                "description": profile.description,
                "service_area": profile.service_area,
                "contact_email": profile.contact_email,
                "contact_phone": profile.contact_phone,
                "website": profile.website,
                "status": profile.status,
                "submitted_at": profile.submitted_at.isoformat() if profile.submitted_at else None,
                "approved_at": profile.approved_at.isoformat() if profile.approved_at else None,
                "rejected_at": profile.rejected_at.isoformat() if profile.rejected_at else None,
                "rejection_reason": profile.rejection_reason,
            }
            for profile in pending
        ])

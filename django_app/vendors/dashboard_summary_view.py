from dataclasses import asdict

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from application.vendors.commands import AuthenticatedActor
from application.vendors.queries import GetVendorDashboardSummaryQuery
from django_app.common.permissions import IsVendor

from .api_contracts import map_vendor_exception
from .services import get_query_handlers
from .views import _get_current_vendor_profile


class VendorDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        profile, error_response = _get_current_vendor_profile(
            request,
            require_workspace=True,
        )
        if error_response:
            return error_response
        try:
            query = GetVendorDashboardSummaryQuery(
                actor=AuthenticatedActor(request.user.id),
                vendor_id=profile.id,
            )
            result = get_query_handlers().get_dashboard_summary(query)
            return Response(asdict(result))
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise

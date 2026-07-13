from dataclasses import asdict

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from application.vendors.queries import (
    GetVendorAnalyticsQuery,
    GetVendorDashboardSummaryQuery,
    ListRecentVendorActivityQuery,
)
from django_app.common.api_responses import api_error
from django_app.common.permissions import IsVendor
from domain.vendors.interfaces import PageRequest

from ..api_contracts import map_vendor_exception
from ..services import get_query_handlers
from ..vendor_view_common import _actor, _get_current_vendor_profile


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
                actor=_actor(request),
                vendor_id=profile.id,
            )
            result = get_query_handlers().get_dashboard_summary(query)
            return Response(asdict(result))
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise


class VendorAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        try:
            query = GetVendorAnalyticsQuery(
                actor=_actor(request),
                vendor_id=profile.id,
            )
            return Response(asdict(get_query_handlers().get_analytics(query)))
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise


class VendorActivityView(APIView):
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        profile, error_response = _get_current_vendor_profile(request, require_workspace=True)
        if error_response:
            return error_response
        raw_limit = request.query_params.get("limit", "10")
        try:
            limit = int(raw_limit)
            if limit < 1 or limit > 100:
                raise ValueError
        except (TypeError, ValueError):
            return api_error(
                code="vendor_activity_limit_invalid",
                message="Activity limit must be an integer from 1 to 100.",
                field_errors={"limit": ["Enter an integer from 1 to 100."]},
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        try:
            query = ListRecentVendorActivityQuery(
                actor=_actor(request),
                vendor_id=profile.id,
                page=PageRequest(limit=limit, offset=0),
            )
            return Response([asdict(item) for item in get_query_handlers().get_recent_activity(query).items])
        except Exception as exc:
            mapped = map_vendor_exception(exc)
            if mapped is not None:
                return mapped
            raise

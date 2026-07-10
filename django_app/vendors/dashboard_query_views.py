from __future__ import annotations

from dataclasses import asdict

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from application.vendors.commands import AuthenticatedActor
from application.vendors.queries import (
    GetVendorAnalyticsQuery,
    GetVendorDashboardSummaryQuery,
    ListRecentVendorActivityQuery,
)
from django_app.common.permissions import IsVendor
from domain
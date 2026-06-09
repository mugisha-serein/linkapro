from django.urls import path
from .views import (
    FlagContentCreateView,
    AdminMetricsView,
    AdminUserListView,
    AdminUserBanView,
    AdminUserReinstateView,
    AdminVendorApproveView,
    AdminVendorRejectView,
    AdminFlagListView,
    AdminFlagResolveView,
    AdminAuditLogListView,
)

urlpatterns = [
    path("flags/", FlagContentCreateView.as_view(), name="flag-content"),
    path("metrics/", AdminMetricsView.as_view(), name="admin-metrics"),
    path("admin/users/", AdminUserListView.as_view(), name="admin-users"),
    path("admin/users/<uuid:user_id>/ban/", AdminUserBanView.as_view(), name="admin-user-ban"),
    path("admin/users/<uuid:user_id>/reinstate/", AdminUserReinstateView.as_view(), name="admin-user-reinstate"),
    path("admin/vendors/<uuid:vendor_id>/approve/", AdminVendorApproveView.as_view(), name="admin-vendor-approve"),
    path("admin/vendors/<uuid:vendor_id>/reject/", AdminVendorRejectView.as_view(), name="admin-vendor-reject"),
    path("admin/flags/", AdminFlagListView.as_view(), name="admin-flags"),
    path("admin/flags/<uuid:flag_id>/resolve/", AdminFlagResolveView.as_view(), name="admin-flag-resolve"),
    path("admin/audit-logs/", AdminAuditLogListView.as_view(), name="admin-audit-logs"),
]

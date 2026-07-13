from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.urls import reverse, path
from django.utils.html import format_html
from django.shortcuts import render, redirect

from django_app.vendors.models import VendorProfile
from django_app.identity.models import User
from .models import AuditLog, ContentFlag, PlatformMetric
from .services import get_command_handlers
from application.governance.commands import (
    BanUserCommand, ReinstateUserCommand, ResolveFlagCommand, GenerateMetricsCommand
)
from application.vendors.commands import (
    ApproveVendorCommand,
    ModeratorActor,
    RejectVendorCommand,
)
from django_app.vendors.services import get_command_handlers as get_vendor_command_handlers


def _moderator(request) -> ModeratorActor:
    return ModeratorActor(user_id=request.user.id)


def _admin_id(request):
    return request.user.id


class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ["business_name", "category", "user_email", "status", "submitted_at", "action_buttons"]
    list_filter = ["status", "category"]
    search_fields = ["business_name", "user__email"]
    actions = ["approve_selected", "reject_selected"]

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "User Email"
    user_email.admin_order_field = "user__email"

    def action_buttons(self, obj):
        if obj.status == "pending_review":
            return format_html(
                '<a class="button" href="{}">Approve</a>&nbsp;'
                '<a class="button" href="{}">Reject</a>',
                reverse("admin:approve-vendor", args=[obj.pk]),
                reverse("admin:reject-vendor", args=[obj.pk]),
            )
        return ""
    action_buttons.short_description = "Actions"

    def approve_selected(self, request, queryset):
        handlers = get_vendor_command_handlers()
        for vendor in queryset.filter(status="pending_review"):
            cmd = ApproveVendorCommand(
                moderator=_moderator(request),
                vendor_id=vendor.id,
                expected_version=vendor.version,
            )
            handlers.approve_vendor(cmd)
        self.message_user(request, "Selected vendors approved.")
    approve_selected.short_description = "Approve selected vendors"

    def reject_selected(self, request, queryset):
        reason = request.POST.get("reason", "Rejected by admin")
        handlers = get_vendor_command_handlers()
        for vendor in queryset.filter(status="pending_review"):
            cmd = RejectVendorCommand(
                moderator=_moderator(request),
                vendor_id=vendor.id,
                expected_version=vendor.version,
                reason=reason,
            )
            handlers.reject_vendor(cmd)
        self.message_user(request, "Selected vendors rejected.")
    reject_selected.short_description = "Reject selected vendors"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:vendor_id>/approve/', self.admin_site.admin_view(self.approve_view), name='approve-vendor'),
            path('<uuid:vendor_id>/reject/', self.admin_site.admin_view(self.reject_view), name='reject-vendor'),
        ]
        return custom_urls + urls

    def approve_view(self, request, vendor_id):
        vendor = VendorProfile.objects.get(id=vendor_id)
        handlers = get_vendor_command_handlers()
        cmd = ApproveVendorCommand(
            moderator=_moderator(request),
            vendor_id=vendor.id,
            expected_version=vendor.version,
        )
        handlers.approve_vendor(cmd)
        self.message_user(request, f"{vendor.business_name} approved.")
        return redirect("admin:vendors_vendorprofile_changelist")

    def reject_view(self, request, vendor_id):
        if request.method == "POST":
            reason = request.POST.get("reason")
            vendor = VendorProfile.objects.get(id=vendor_id)
            handlers = get_vendor_command_handlers()
            cmd = RejectVendorCommand(
                moderator=_moderator(request),
                vendor_id=vendor.id,
                expected_version=vendor.version,
                reason=reason,
            )
            handlers.reject_vendor(cmd)
            self.message_user(request, f"{vendor.business_name} rejected.")
            return redirect("admin:vendors_vendorprofile_changelist")
        return render(request, "admin/reject_vendor.html", {"vendor_id": vendor_id})


class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "first_name", "last_name", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    actions = ["ban_selected", "reinstate_selected"]

    def ban_selected(self, request, queryset):
        handlers = get_command_handlers()
        for user in queryset:
            cmd = BanUserCommand(admin_id=_admin_id(request), user_id=user.id)
            handlers.ban_user(cmd)
        self.message_user(request, "Selected users banned.")
    ban_selected.short_description = "Ban selected users"

    def reinstate_selected(self, request, queryset):
        handlers = get_command_handlers()
        for user in queryset:
            cmd = ReinstateUserCommand(admin_id=_admin_id(request), user_id=user.id)
            handlers.reinstate_user(cmd)
        self.message_user(request, "Selected users reinstated.")
    reinstate_selected.short_description = "Reinstate selected users"


class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["admin", "action_type", "target_type", "target_id", "created_at"]
    list_filter = ["action_type", "target_type"]
    search_fields = ["admin__email", "target_id"]
    readonly_fields = ["id", "admin", "action_type", "target_type", "target_id", "details", "created_at"]


class ContentFlagAdmin(admin.ModelAdmin):
    list_display = ["content_type", "content_id", "reported_by", "status", "created_at"]
    list_filter = ["status", "content_type"]
    actions = ["mark_reviewed", "dismiss_selected"]

    def mark_reviewed(self, request, queryset):
        handlers = get_command_handlers()
        for flag in queryset:
            cmd = ResolveFlagCommand(admin_id=_admin_id(request), flag_id=flag.id, dismiss=False)
            handlers.resolve_flag(cmd)
        self.message_user(request, "Flags marked as reviewed.")
    mark_reviewed.short_description = "Mark as reviewed"

    def dismiss_selected(self, request, queryset):
        handlers = get_command_handlers()
        for flag in queryset:
            cmd = ResolveFlagCommand(admin_id=_admin_id(request), flag_id=flag.id, dismiss=True)
            handlers.resolve_flag(cmd)
        self.message_user(request, "Flags dismissed.")
    dismiss_selected.short_description = "Dismiss selected flags"


class PlatformMetricAdmin(admin.ModelAdmin):
    list_display = ["date", "total_users", "total_vendors", "active_vendors", "pending_vendor_approvals"]
    readonly_fields = ["date", "updated_at"]
    actions = ["generate_today_metrics"]

    def generate_today_metrics(self, request, queryset):
        handlers = get_command_handlers()
        metric = handlers.generate_metrics(GenerateMetricsCommand())
        self.message_user(request, f"Metrics for {metric.date} generated.")
    generate_today_metrics.short_description = "Generate today's metrics"


# Register with safe unregister
try:
    admin.site.unregister(VendorProfile)
except NotRegistered:
    pass

try:
    admin.site.unregister(User)
except NotRegistered:
    pass

admin.site.register(VendorProfile, VendorProfileAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(AuditLog, AuditLogAdmin)
admin.site.register(ContentFlag, ContentFlagAdmin)
admin.site.register(PlatformMetric, PlatformMetricAdmin)

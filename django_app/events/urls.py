from django.urls import path
from .views import (
    EventListCreateView,
    EventDetailView,
    ChecklistListCreateView,
    ChecklistItemListCreateView,
    ChecklistItemDetailView,
    BudgetLineListCreateView,
    BudgetLineDetailView,
    GuestListCreateView,
    GuestDetailView,
    TimelineBlockListCreateView,
    TimelineBlockDetailView,
    EventVendorAssignmentListCreateView,
    EventVendorAssignmentDetailView,
    DashboardSummaryView,
)

urlpatterns = [
    path("", EventListCreateView.as_view(), name="event-list"),
    path("dashboard-summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("<uuid:event_id>/", EventDetailView.as_view(), name="event-detail"),
    path("<uuid:event_id>/checklists/", ChecklistListCreateView.as_view(), name="event-checklists"),
    path("<uuid:event_id>/budget-lines/", BudgetLineListCreateView.as_view(), name="event-budget-lines"),
    path("<uuid:event_id>/guests/", GuestListCreateView.as_view(), name="event-guests"),
    path("<uuid:event_id>/timeline-blocks/", TimelineBlockListCreateView.as_view(), name="event-timeline-blocks"),
    path("<uuid:event_id>/vendors/", EventVendorAssignmentListCreateView.as_view(), name="event-vendors"),
    path("<uuid:event_id>/vendors/<uuid:assignment_id>/", EventVendorAssignmentDetailView.as_view(), name="event-vendor-detail"),
    path("checklists/<uuid:checklist_id>/items/", ChecklistItemListCreateView.as_view(), name="checklist-items"),
    path("checklist-items/<uuid:item_id>/", ChecklistItemDetailView.as_view(), name="checklist-item-detail"),
    path("budget-lines/<uuid:line_id>/", BudgetLineDetailView.as_view(), name="budget-line-detail"),
    path("guests/<uuid:guest_id>/", GuestDetailView.as_view(), name="guest-detail"),
    path("timeline-blocks/<uuid:block_id>/", TimelineBlockDetailView.as_view(), name="timeline-block-detail"),
]

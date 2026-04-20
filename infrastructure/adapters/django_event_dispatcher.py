from django.dispatch import Signal

# Define signals for each domain event
user_registered = Signal()
user_logged_in = Signal()
user_password_changed = Signal()
user_oauth_linked = Signal()
user_deactivated = Signal()

# Define events signals
event_created = Signal()
checklist_created = Signal()
budget_line_added = Signal()
guest_added = Signal()
timeline_block_added = Signal()

# Define the event dispatcher
vendor_submitted_for_review = Signal()
vendor_approved = Signal()
vendor_rejected = Signal()
vendor_suspended = Signal()
inquiry_received = Signal()

class DjangoEventDispatcher:
    def dispatch(self, event) -> None:
        event_type = type(event).__name__
        signal_map = {
            # identity
            "UserRegistered": user_registered,
            "UserLoggedIn": user_logged_in,
            "UserPasswordChanged": user_password_changed,
            "UserOAuthLinked": user_oauth_linked,
            "UserDeactivated": user_deactivated,

            # events
            "EventCreated": event_created,
            "ChecklistCreated": checklist_created,
            "BudgetLineAdded": budget_line_added,
            "GuestAdded": guest_added,
            "TimelineBlockAdded": timeline_block_added,

            # vendors
            "VendorSubmittedForReview": vendor_submitted_for_review,
            "VendorApproved": vendor_approved,
            "VendorRejected": vendor_rejected,
            "VendorSuspended": vendor_suspended,
            "InquiryReceived": inquiry_received,
        }
        signal = signal_map.get(event_type)
        if signal:
            signal.send(sender=self.__class__, event=event)
"""Legacy in-process signal dispatcher for domains without an outbox.

Identity and vendors use their domain outbox dispatchers as the single live
event mechanism for aggregate side effects.
"""

import logging

from django.db import transaction
from django.dispatch import Signal

logger = logging.getLogger(__name__)

# Define events signals
event_created = Signal()
checklist_created = Signal()
budget_line_added = Signal()
guest_added = Signal()
timeline_block_added = Signal()

export_requested = Signal()

class DjangoEventDispatcher:
    def dispatch(self, event) -> None:
        event_type = type(event).__name__
        signal_map = {
            # events
            "EventCreated": event_created,
            "ChecklistCreated": checklist_created,
            "BudgetLineAdded": budget_line_added,
            "GuestAdded": guest_added,
            "TimelineBlockAdded": timeline_block_added,

            # documents
            "ExportRequested": export_requested,
        }
        signal = signal_map.get(event_type)
        if signal:
            signal.send(sender=self.__class__, event=event)

    def dispatch_after_commit(self, event) -> None:
        def _dispatch() -> None:
            try:
                self.dispatch(event)
            except Exception:
                logger.exception("Failed to dispatch payment domain event after commit", extra={"event_type": type(event).__name__})

        transaction.on_commit(_dispatch)

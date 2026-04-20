import asyncio
from collections import defaultdict
from typing import Any, Callable, Dict, List


class FastAPIEventDispatcher:
    """Simple in‑process event dispatcher for FastAPI."""
    
    _handlers: Dict[str, List[Callable]] = defaultdict(list)

    @classmethod
    def register(cls, event_type: str, handler: Callable) -> None:
        """Register a handler for a specific event type."""
        cls._handlers[event_type].append(handler)

    def dispatch(self, event: Any) -> None:
        """Dispatch an event to all registered handlers."""
        event_type = type(event).__name__
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                # Run async handlers in the background
                asyncio.create_task(handler(event))
            else:
                handler(event)
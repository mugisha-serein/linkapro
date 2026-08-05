from dataclasses import dataclass, field


@dataclass
class AggregateRoot:
    _events: list[object] = field(default_factory=list, init=False, repr=False)

    def _record_event(self, event: object) -> None:
        self._events.append(event)

    def pull_events(self) -> list[object]:
        events = list(self._events)
        self._events.clear()
        return events

"""Normalized events and the synchronous in-process event bus."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping


@dataclass(frozen=True)
class Event:
    version: int
    source: str
    type: str
    timestamp: str
    data: Mapping[str, object]

    @classmethod
    def create(cls, source: str, event_type: str, data: Mapping[str, object]) -> "Event":
        return cls(
            version=1,
            source=source,
            type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=dict(data),
        )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def publish(self, event: Event) -> None:
        for subscriber in tuple(self._subscribers):
            subscriber(event)

"""Common lifecycle contract for independently runnable system adapters."""

from __future__ import annotations

import threading
from typing import Protocol

from cyber_companion.events import EventBus


class SystemAdapter(Protocol):
    def run(self, bus: EventBus, stop_event: threading.Event) -> None: ...

    def stop(self) -> None: ...

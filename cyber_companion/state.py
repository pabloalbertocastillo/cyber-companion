"""State reduction and persistent runtime snapshot."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from cyber_companion.events import Event
from cyber_companion.presentation import PresentationCommand
from cyber_companion.runtime import atomic_write_text


class StateStore:
    def __init__(
        self,
        state_path: Path,
        initial_presentation: PresentationCommand,
    ) -> None:
        self.state_path = state_path
        self.presentation = initial_presentation
        self.domains: dict[str, dict[str, object]] = {}
        self.media: dict[str, object] = {
            "player": None,
            "status": "stopped",
            "track_id": "",
            "artist": "",
            "title": "",
        }
        self.last_event: dict[str, object] | None = None

    def initialize(self) -> None:
        self._persist()

    def handle(self, event: Event) -> None:
        domain = event.type.partition(".")[0]
        self.domains.setdefault(domain, {}).update(event.data)
        if domain == "media":
            self.media.update(event.data)
        self.last_event = event.as_dict()
        self._persist()

    def set_presentation(self, presentation: PresentationCommand) -> None:
        if presentation == self.presentation:
            return
        self.presentation = presentation
        self._persist()

    def behavior_state(self) -> dict[str, object]:
        return {"domains": {name: dict(value) for name, value in self.domains.items()}}

    def snapshot(self) -> dict[str, object]:
        return {
            "version": 1,
            "presentation": self.presentation.as_dict(),
            "domains": {name: dict(value) for name, value in self.domains.items()},
            "media": dict(self.media),
            "last_event": self.last_event,
        }

    def _persist(self) -> None:
        serialized = json.dumps(self.snapshot(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        atomic_write_text(self.state_path, serialized)

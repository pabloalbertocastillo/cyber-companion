"""State reduction and persistent runtime snapshot."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path

from cyber_companion.events import Event
from cyber_companion.runtime import atomic_write_text


PresentationSubscriber = Callable[[str], None]


class StateStore:
    def __init__(
        self,
        state_path: Path,
        default_profile: str,
        event_profiles: Mapping[str, str],
        on_presentation: PresentationSubscriber,
    ) -> None:
        self.state_path = state_path
        self.default_profile = default_profile
        self.event_profiles = dict(event_profiles)
        self.on_presentation = on_presentation
        self.profile = default_profile
        self.media: dict[str, object] = {
            "player": None,
            "status": "stopped",
            "track_id": "",
            "artist": "",
            "title": "",
        }
        self.last_event: dict[str, object] | None = None

    def initialize(self, publish_presentation: bool = True) -> None:
        self._persist()
        if publish_presentation:
            self.on_presentation(self.profile)

    def handle(self, event: Event) -> None:
        previous_profile = self.profile
        if event.source == "mpris" and event.type.startswith("media."):
            self.media.update(event.data)

        selected_profile = self.event_profiles.get(event.type)
        if selected_profile is not None:
            self.profile = selected_profile

        self.last_event = event.as_dict()
        self._persist()
        if self.profile != previous_profile:
            self.on_presentation(self.profile)

    def snapshot(self) -> dict[str, object]:
        return {
            "version": 1,
            "presentation": {"profile": self.profile},
            "media": dict(self.media),
            "last_event": self.last_event,
        }

    def _persist(self) -> None:
        serialized = json.dumps(self.snapshot(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        atomic_write_text(self.state_path, serialized)

"""Native media-state control for the patched Wayland V-Pets renderer."""

from __future__ import annotations

import os
import signal
from collections.abc import Callable, Iterable

from cyber_companion.presentation import PresentationCommand


RendererNotifier = Callable[[int, int], None]


def notify_renderer(process_id: int, signal_number: int) -> None:
    os.kill(process_id, signal_number)


class MediaSignalRendererAdapter:
    """Map presentation profiles to renderer-owned real-time signals."""

    def __init__(
        self,
        renderer_pid: int,
        profiles: Iterable[str],
        notifier: RendererNotifier = notify_renderer,
    ) -> None:
        self.renderer_pid = renderer_pid
        self.profiles = frozenset(profiles)
        self.notifier = notifier
        self._current_profile: str | None = None

    def apply(self, command: PresentationCommand) -> bool:
        profile = command.profile
        if profile == self._current_profile:
            return False
        if profile not in self.profiles:
            raise ValueError(f"unknown presentation profile: {profile}")

        if profile == "media":
            signal_number = int(signal.SIGRTMIN)
        elif profile == "idle":
            signal_number = int(signal.SIGRTMIN) + 1
        else:
            raise ValueError(f"profile has no native renderer signal: {profile}")

        self.notifier(self.renderer_pid, signal_number)
        self._current_profile = profile
        return True

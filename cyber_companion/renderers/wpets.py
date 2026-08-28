"""Wayland V-Pets runtime-config adapter."""

from __future__ import annotations

import os
import signal
from collections.abc import Callable, Mapping
from pathlib import Path

from cyber_companion.runtime import atomic_write_text


def render_config(base_config: str, overrides: Mapping[str, object]) -> str:
    pending = {key: str(value) for key, value in overrides.items()}
    output: list[str] = []

    for line in base_config.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue

        key = stripped.split("=", 1)[0].strip()
        if key in pending:
            newline = "\n" if line.endswith("\n") else ""
            output.append(f"{key}={pending.pop(key)}{newline}")
        else:
            output.append(line)

    if pending:
        missing = ", ".join(sorted(pending))
        raise ValueError(f"profile overrides unknown wpets keys: {missing}")

    return "".join(output)


def notify_renderer(process_id: int) -> None:
    os.kill(process_id, signal.SIGUSR2)


class WpetsRendererAdapter:
    def __init__(
        self,
        base_config_path: Path,
        runtime_config_path: Path,
        profiles: Mapping[str, Mapping[str, object]],
        renderer_pid: int,
        notifier: Callable[[int], None] = notify_renderer,
    ) -> None:
        self.base_config_path = base_config_path
        self.runtime_config_path = runtime_config_path
        self.profiles = profiles
        self.renderer_pid = renderer_pid
        self.notifier = notifier
        self._current_profile: str | None = None

    def apply(self, profile: str) -> bool:
        if profile == self._current_profile:
            return False
        if profile not in self.profiles:
            raise ValueError(f"unknown presentation profile: {profile}")

        profile_data = self.profiles[profile]
        wpets_overrides = profile_data.get("wpets")
        if not isinstance(wpets_overrides, Mapping):
            raise ValueError(f"profile {profile!r} has no wpets mapping")

        base_config = self.base_config_path.read_text(encoding="utf-8")
        runtime_config = render_config(base_config, wpets_overrides)
        atomic_write_text(self.runtime_config_path, runtime_config)
        self.notifier(self.renderer_pid)
        self._current_profile = profile
        return True

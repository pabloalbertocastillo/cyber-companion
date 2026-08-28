"""Cyber Companion v0.9 event controller."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from collections.abc import Mapping
from pathlib import Path

from cyber_companion.adapters.mpris import PlayerctlMprisAdapter
from cyber_companion.events import Event, EventBus
from cyber_companion.renderers.media_signals import MediaSignalRendererAdapter
from cyber_companion.state import StateStore


def load_profiles(path: Path) -> tuple[str, dict[str, str], dict[str, Mapping[str, object]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("unsupported system profile version")

    default_profile = data.get("default_profile")
    event_profiles = data.get("event_profiles")
    profiles = data.get("profiles")
    if not isinstance(default_profile, str):
        raise ValueError("default_profile must be a string")
    if not isinstance(event_profiles, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in event_profiles.items()
    ):
        raise ValueError("event_profiles must map event names to profile names")
    if not isinstance(profiles, dict) or default_profile not in profiles:
        raise ValueError("profiles must contain default_profile")
    if not all(isinstance(key, str) and isinstance(value, dict) for key, value in profiles.items()):
        raise ValueError("profiles must be named objects")
    unknown_profiles = sorted(set(event_profiles.values()) - set(profiles))
    if unknown_profiles:
        raise ValueError(f"event_profiles reference unknown profiles: {', '.join(unknown_profiles)}")

    return default_profile, event_profiles, profiles


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Connect Cyber Companion to normalized system events")
    parser.add_argument("--playerctl", default="playerctl", help="playerctl executable")
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--renderer-pid", required=True, type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    default_profile, event_profiles, profiles = load_profiles(args.profiles)

    renderer = MediaSignalRendererAdapter(
        renderer_pid=args.renderer_pid,
        profiles=profiles,
    )
    state = StateStore(
        state_path=args.state_file,
        default_profile=default_profile,
        event_profiles=event_profiles,
        on_presentation=renderer.apply,
    )
    bus = EventBus()

    def print_event(event: Event) -> None:
        print(json.dumps(event.as_dict(), ensure_ascii=False, sort_keys=True), flush=True)

    bus.subscribe(print_event)
    bus.subscribe(state.handle)

    stop_event = threading.Event()
    adapter = PlayerctlMprisAdapter(executable=args.playerctl)

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()
        adapter.stop()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    # The renderer starts in Idle. The first normalized media event establishes
    # the live state without rewriting or reloading its configuration.
    state.initialize(publish_presentation=False)
    print(f"Cyber Companion controller: media=all-mpris state={args.state_file}", flush=True)
    adapter.run(bus, stop_event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

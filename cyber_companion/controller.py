"""Cyber Companion extensible system-behavior controller."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path

from cyber_companion.adapters.base import SystemAdapter
from cyber_companion.adapters.registry import build_adapters, load_adapter_specs
from cyber_companion.behavior import load_behavior_engine
from cyber_companion.director import BehaviorDirector
from cyber_companion.events import Event, EventBus
from cyber_companion.renderers.media_signals import MediaSignalRendererAdapter
from cyber_companion.state import StateStore


def load_profiles(path: Path) -> dict[str, dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("unsupported system profile version")

    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("profiles must be an object")
    if not all(isinstance(key, str) and isinstance(value, dict) for key, value in profiles.items()):
        raise ValueError("profiles must be named objects")
    return profiles


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Connect Cyber Companion to normalized system events")
    parser.add_argument("--adapters", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--behaviors", required=True, type=Path)
    parser.add_argument("--state-file", required=True, type=Path)
    parser.add_argument("--renderer-pid", required=True, type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    profiles = load_profiles(args.profiles)
    engine = load_behavior_engine(args.behaviors)
    adapters = build_adapters(load_adapter_specs(args.adapters))
    configured_profiles = {engine.default.profile, *(rule.command.profile for rule in engine.rules)}
    unknown_profiles = sorted(configured_profiles - set(profiles))
    if unknown_profiles:
        raise ValueError(f"behaviors reference unknown renderer profiles: {', '.join(unknown_profiles)}")

    renderer = MediaSignalRendererAdapter(
        renderer_pid=args.renderer_pid,
        profiles=profiles,
    )
    state = StateStore(
        state_path=args.state_file,
        initial_presentation=engine.default,
    )
    director = BehaviorDirector(state=state, engine=engine, renderer=renderer)
    bus = EventBus()

    def print_event(event: Event) -> None:
        print(json.dumps(event.as_dict(), ensure_ascii=False, sort_keys=True), flush=True)

    bus.subscribe(print_event)
    bus.subscribe(director.handle)

    stop_event = threading.Event()
    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()
        for _name, adapter in adapters:
            adapter.stop()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    # The renderer starts in Idle. The first normalized media event establishes
    # the live state without rewriting or reloading its configuration.
    director.initialize(publish=False)
    adapter_names = ",".join(name for name, _adapter in adapters)
    print(f"Cyber Companion director: adapters={adapter_names} state={args.state_file}", flush=True)

    def run_adapter(name: str, adapter: SystemAdapter) -> None:
        try:
            adapter.run(bus, stop_event)
        except Exception as error:
            bus.publish(Event.create(name, "adapter.failed", {"error": str(error)}))

    threads = [
        threading.Thread(target=run_adapter, args=(name, adapter), name=f"adapter-{name}")
        for name, adapter in adapters
    ]
    for thread in threads:
        thread.start()
    while not stop_event.wait(0.25) and any(thread.is_alive() for thread in threads):
        pass
    stop_event.set()
    for _name, adapter in adapters:
        adapter.stop()
    for thread in threads:
        thread.join(timeout=4.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

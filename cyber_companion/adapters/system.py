"""Dependency-free Linux telemetry with time-based busy hysteresis."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

from cyber_companion.events import Event, EventBus


Clock = Callable[[], float]


class BusyLatch:
    def __init__(self, enter_above: float, enter_for: float, exit_below: float,
                 exit_for: float, clock: Clock = time.monotonic) -> None:
        if not 0 <= exit_below < enter_above <= 1:
            raise ValueError("busy thresholds must satisfy 0 <= exit_below < enter_above <= 1")
        if enter_for < 0 or exit_for < 0:
            raise ValueError("busy durations must not be negative")
        self.enter_above = enter_above
        self.enter_for = enter_for
        self.exit_below = exit_below
        self.exit_for = exit_for
        self.clock = clock
        self.busy = False
        self._candidate_since: float | None = None

    def update(self, cpu_ratio: float) -> bool:
        now = self.clock()
        qualifies = cpu_ratio <= self.exit_below if self.busy else cpu_ratio >= self.enter_above
        required = self.exit_for if self.busy else self.enter_for
        if not qualifies:
            self._candidate_since = None
            return self.busy
        if self._candidate_since is None:
            self._candidate_since = now
        if now - self._candidate_since >= required:
            self.busy = not self.busy
            self._candidate_since = None
        return self.busy


def read_cpu_times(path: Path = Path("/proc/stat")) -> tuple[int, int]:
    fields = path.read_text(encoding="utf-8").splitlines()[0].split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise ValueError("invalid /proc/stat cpu line")
    values = [int(value) for value in fields[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def cpu_ratio(previous: tuple[int, int], current: tuple[int, int]) -> float:
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - idle_delta / total_delta))


def read_memory_ratio(path: Path = Path("/proc/meminfo")) -> float:
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, remainder = line.partition(":")
        if separator and key in {"MemTotal", "MemAvailable"}:
            values[key] = int(remainder.split()[0])
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    if total <= 0:
        raise ValueError("MemTotal is missing from /proc/meminfo")
    return max(0.0, min(1.0, 1.0 - available / total))


def read_temperature_c(root: Path = Path("/sys/class/hwmon")) -> float | None:
    readings: list[float] = []
    for path in root.glob("hwmon*/temp*_input"):
        try:
            value = float(path.read_text(encoding="utf-8").strip()) / 1000.0
        except (OSError, ValueError):
            continue
        if 0.0 < value < 150.0:
            readings.append(value)
    return max(readings) if readings else None


class LinuxSystemAdapter:
    def __init__(self, interval_seconds: float = 2.0, busy_above: float = 0.70,
                 busy_for_seconds: float = 4.0, idle_below: float = 0.40,
                 idle_for_seconds: float = 6.0, thermal_warning_c: float = 80.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("system interval_seconds must be positive")
        self.interval_seconds = interval_seconds
        self.thermal_warning_c = thermal_warning_c
        self.latch = BusyLatch(busy_above, busy_for_seconds, idle_below, idle_for_seconds)
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self, bus: EventBus, stop_event: threading.Event) -> None:
        previous = read_cpu_times()
        previous_busy = self.latch.busy
        while not stop_event.is_set() and not self._stop.wait(self.interval_seconds):
            current = read_cpu_times()
            usage = cpu_ratio(previous, current)
            previous = current
            busy = self.latch.update(usage)
            temperature = read_temperature_c()
            data: dict[str, object] = {
                "cpu_ratio": round(usage, 4),
                "memory_ratio": round(read_memory_ratio(), 4),
                "temperature_c": None if temperature is None else round(temperature, 1),
                "busy": busy,
                "thermal_alert": temperature is not None and temperature >= self.thermal_warning_c,
            }
            bus.publish(Event.create("linux_system", "system.telemetry", data))
            if busy != previous_busy:
                bus.publish(Event.create("linux_system", "system.busy" if busy else "system.idle", data))
                previous_busy = busy

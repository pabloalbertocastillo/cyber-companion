"""Bounded read-only adapters. No renderer, notification or action imports."""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from .adapters.system import read_cpu_times, cpu_ratio, read_memory_ratio
from .adapters.mpris import parse_playerctl_line, PLAYERCTL_FORMAT


def short(value: str, size=256) -> str:
    return value.encode("utf-8")[:size].decode("utf-8", errors="ignore")


async def command(*argv: str, timeout: float = 2, limit: int = 65536, allow_empty: bool = False) -> str:
    process = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.DEVNULL)
    async def collect():
        result = bytearray()
        while True:
            block = await process.stdout.read(min(4096, limit + 1 - len(result)))
            if not block:
                break
            result.extend(block)
            if len(result) > limit:
                raise ValueError("command output limit exceeded")
        code = await process.wait()
        if code != 0 and not (allow_empty and code == 1 and not result):
            raise OSError("adapter command failed")
        return result.decode("utf-8", errors="replace")
    try:
        return await asyncio.wait_for(collect(), timeout)
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


class Linux:
    def __init__(self):
        self.previous = None

    def sample(self) -> dict:
        current = read_cpu_times()
        cpu = None if self.previous is None else cpu_ratio(self.previous, current)
        self.previous = current
        try:
            memory = read_memory_ratio()
        except (ValueError, OSError):
            memory = None
        temperatures = []
        for path in sorted(Path("/sys/class/hwmon").glob("hwmon*/temp*_input"))[:64]:
            try:
                temperature = float(path.read_text()) / 1000
                limit_path = path.with_name(path.name.replace("_input", "_max"))
                limit = float(limit_path.read_text()) / 1000 if limit_path.exists() else 85.0
                label_path = path.with_name(path.name.replace("_input", "_label"))
                label = label_path.read_text().strip() if label_path.exists() else path.stem
                name = (path.parent / "name").read_text().strip()
                # Ignore non-CPU devices without an explicit device limit.
                if not limit_path.exists() and name not in ("coretemp", "k10temp", "zenpower", "cpu_thermal"):
                    continue
                if -50 <= temperature <= 200 and 20 <= limit <= 150:
                    temperatures.append((temperature - limit, temperature, limit, f"{name}/{label}"))
            except (ValueError, OSError):
                continue
        chosen = max(temperatures) if temperatures else None
        result = {"cpu_ratio": cpu, "memory_ratio": memory,
                  "temperature_c": chosen[1] if chosen else None,
                  "temperature_limit_c": chosen[2] if chosen else None,
                  "sensor": chosen[3] if chosen else ""}
        for name in ("cpu", "memory", "io"):
            try:
                text = Path(f"/proc/pressure/{name}").read_text()
                result[f"psi_{name}"] = float(re.search(r"some avg10=([\d.]+)", text).group(1))
            except (OSError, ValueError, AttributeError):
                result[f"psi_{name}"] = None
        return result


def storage(paths: list[str]) -> dict:
    mounts = []
    for name in paths:
        stat = os.statvfs(name)
        total, available = stat.f_blocks * stat.f_frsize, stat.f_bavail * stat.f_frsize
        if total > 0:
            mounts.append({"path": name, "available": available, "total": total,
                           "ratio": min(1, max(0, available / total))})
    return {"mounts": mounts}


def network() -> dict:
    up = []
    for device in sorted(Path("/sys/class/net").iterdir())[:64]:
        try:
            if device.name != "lo" and (device / "operstate").read_text().strip() == "up":
                up.append(device.name)
        except OSError:
            continue
    route = False
    known = False
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            f = line.split()
            if len(f) >= 4 and f[0] != "lo" and f[1] == "00000000" and int(f[3], 16) & 1:
                route = True
        known = True
    except OSError:
        pass
    try:
        for line in Path("/proc/net/ipv6_route").read_text().splitlines():
            f = line.split()
            if len(f) >= 10 and f[0] == "0" * 32 and f[1] == "00" and f[-1] != "lo" and int(f[8], 16) & 1:
                route = True
        known = True
    except OSError:
        pass
    return {"interfaces": up, "default_route": route if known else None}


async def media() -> dict:
    text = await command("playerctl", "--all-players", "metadata", "--format", PLAYERCTL_FORMAT, allow_empty=True)
    players = [parse_playerctl_line(line) for line in text.splitlines()[:32]]
    players = [p for p in players if p]
    players.sort(key=lambda p: (p.status != "playing", p.status != "paused", p.instance))
    p = players[0] if players else None
    return {"status": p.status if p else "stopped", "player": p.instance if p else "",
            "title": short(p.title) if p else "", "artist": short(p.artist) if p else ""}


async def desktop() -> dict:
    monitors, window = await asyncio.gather(command("hyprctl", "-j", "monitors"), command("hyprctl", "-j", "activewindow"))
    outputs = json.loads(monitors)
    if type(outputs) is not list or not outputs or any(type(m) is not dict for m in outputs):
        raise ValueError("no compositor outputs")
    focused = next((m for m in outputs if m.get("focused")), outputs[0])
    active = json.loads(window)
    if type(active) is not dict or type(focused.get("activeWorkspace", {})) is not dict:
        raise ValueError("invalid compositor state")
    return {"monitor": str(focused.get("name", "")),
            "workspace": str(focused.get("activeWorkspace", {}).get("name", "")),
            "fullscreen": bool(active.get("fullscreen", 0)),
            "outputs": [str(m["name"]) for m in outputs[:16]]}


async def session() -> dict:
    ident = os.environ.get("XDG_SESSION_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ident):
        return {"locked": None}
    value = (await command("loginctl", "show-session", ident, "--property=LockedHint", "--value")).strip()
    return {"locked": True if value == "yes" else False if value == "no" else None}


async def virtualization() -> dict:
    # Read-only libvirt connection. Enumeration only: never start/stop or edit a VM.
    text = await command("virsh", "--readonly", "--connect", "qemu:///system", "list", "--all", timeout=3)
    vms = []
    for line in text.splitlines()[2:]:
        fields = line.split(None, 2)
        if len(fields) == 3:
            vms.append({"name": short(fields[1],128), "state": short(fields[2],64)})
    return {"vms": vms[:32]}

"""Validated, declarative adapter construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from cyber_companion.adapters.base import SystemAdapter
from cyber_companion.adapters.mpris import PlayerctlMprisAdapter


AdapterFactory = Callable[[Mapping[str, object]], SystemAdapter]


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    type: str
    enabled: bool
    settings: Mapping[str, object]


def _mpris_factory(settings: Mapping[str, object]) -> SystemAdapter:
    unknown = sorted(set(settings) - {"executable"})
    if unknown:
        raise ValueError(f"mpris settings have unknown keys: {', '.join(unknown)}")
    executable = settings.get("executable", "playerctl")
    if not isinstance(executable, str) or not executable:
        raise ValueError("mpris executable must be a non-empty string")
    return PlayerctlMprisAdapter(executable=executable)


ADAPTER_FACTORIES: dict[str, AdapterFactory] = {"mpris": _mpris_factory}


def load_adapter_specs(path: Path) -> list[AdapterSpec]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("unsupported adapter configuration version")
    entries = data.get("adapters")
    if not isinstance(entries, list):
        raise ValueError("adapters must be a list")
    specs: list[AdapterSpec] = []
    names: set[str] = set()
    for index, entry in enumerate(entries):
        location = f"adapters[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{location} must be an object")
        name = entry.get("name")
        adapter_type = entry.get("type")
        enabled = entry.get("enabled", True)
        settings = entry.get("settings", {})
        if not isinstance(name, str) or not name:
            raise ValueError(f"{location}.name must be a non-empty string")
        if name in names:
            raise ValueError(f"duplicate adapter name: {name}")
        if not isinstance(adapter_type, str) or not adapter_type:
            raise ValueError(f"{location}.type must be a non-empty string")
        if not isinstance(enabled, bool):
            raise ValueError(f"{location}.enabled must be a boolean")
        if not isinstance(settings, dict):
            raise ValueError(f"{location}.settings must be an object")
        names.add(name)
        specs.append(AdapterSpec(name, adapter_type, enabled, settings))
    return specs


def build_adapters(
    specs: list[AdapterSpec], factories: Mapping[str, AdapterFactory] = ADAPTER_FACTORIES
) -> list[tuple[str, SystemAdapter]]:
    adapters: list[tuple[str, SystemAdapter]] = []
    for spec in specs:
        if not spec.enabled:
            continue
        factory = factories.get(spec.type)
        if factory is None:
            raise ValueError(f"unknown enabled adapter type: {spec.type}")
        adapters.append((spec.name, factory(spec.settings)))
    if not adapters:
        raise ValueError("at least one adapter must be enabled")
    return adapters

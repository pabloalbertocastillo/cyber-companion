"""Declarative behavior selection independent from adapters and renderers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cyber_companion.presentation import PresentationCommand


def _lookup_path(state: Mapping[str, object], path: str) -> object:
    value: object = state
    for component in path.split("."):
        if not isinstance(value, Mapping) or component not in value:
            return None
        value = value[component]
    return value


@dataclass(frozen=True)
class BehaviorRule:
    name: str
    priority: int
    path: str
    equals: object
    command: PresentationCommand

    def matches(self, state: Mapping[str, object]) -> bool:
        return _lookup_path(state, self.path) == self.equals


class BehaviorEngine:
    def __init__(self, default: PresentationCommand, rules: list[BehaviorRule]) -> None:
        self.default = default
        self.rules = tuple(sorted(rules, key=lambda rule: (-rule.priority, rule.name)))

    def resolve(self, state: Mapping[str, object]) -> PresentationCommand:
        return next((rule.command for rule in self.rules if rule.matches(state)), self.default)


def _parse_command(data: object, location: str) -> PresentationCommand:
    if not isinstance(data, dict):
        raise ValueError(f"{location} must be an object")
    allowed = {"profile", "behavior", "intensity", "transition"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"{location} has unknown keys: {', '.join(unknown)}")
    try:
        return PresentationCommand(
            profile=str(data["profile"]),
            behavior=str(data["behavior"]),
            intensity=float(data.get("intensity", 1.0)),
            transition=str(data.get("transition", "smooth")),
        )
    except KeyError as error:
        raise ValueError(f"{location} is missing {error.args[0]}") from error


def load_behavior_engine(path: Path) -> BehaviorEngine:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("unsupported behavior configuration version")
    default = _parse_command(data.get("default"), "default")
    raw_rules = data.get("behaviors")
    if not isinstance(raw_rules, list):
        raise ValueError("behaviors must be a list")

    rules: list[BehaviorRule] = []
    names: set[str] = set()
    for index, raw_rule in enumerate(raw_rules):
        location = f"behaviors[{index}]"
        if not isinstance(raw_rule, dict):
            raise ValueError(f"{location} must be an object")
        name = raw_rule.get("name")
        priority = raw_rule.get("priority")
        condition = raw_rule.get("when")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{location}.name must be a non-empty string")
        if name in names:
            raise ValueError(f"duplicate behavior name: {name}")
        if not isinstance(priority, int):
            raise ValueError(f"{location}.priority must be an integer")
        if not isinstance(condition, dict) or not isinstance(condition.get("path"), str) or "equals" not in condition:
            raise ValueError(f"{location}.when must contain path and equals")
        names.add(name)
        rules.append(
            BehaviorRule(
                name=name,
                priority=priority,
                path=condition["path"],
                equals=condition["equals"],
                command=_parse_command(raw_rule.get("command"), f"{location}.command"),
            )
        )
    return BehaviorEngine(default, rules)

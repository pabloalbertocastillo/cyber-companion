"""Deterministic observations, temporal detectors and presentation state."""
from __future__ import annotations

import copy
import hashlib
import time
from dataclasses import dataclass
from typing import Any

from .validation import encode, number

LEASES = {"system": 8, "storage": 90, "network": 20, "media": 15, "desktop": 8, "session": 8, "virtualization": 35}


def validate_sample(domain: str, value: dict) -> None:
    encode(value)
    if type(value) is not dict:
        raise ValueError("observation must be an object")
    allowed = {
        "system": {"cpu_ratio", "memory_ratio", "temperature_c", "temperature_limit_c", "sensor", "psi_cpu", "psi_memory", "psi_io"},
        "storage": {"mounts"}, "network": {"interfaces", "default_route"},
        "media": {"status", "player", "title", "artist"},
        "desktop": {"monitor", "workspace", "fullscreen", "outputs"},
        "session": {"locked"}, "virtualization": {"vms"},
    }
    if domain not in allowed or set(value) != allowed[domain]:
        raise ValueError("observation fields do not match registered domain")
    def bounded_strings(item):
        if type(item) is str and len(item.encode("utf-8")) > 256:
            raise ValueError("observation string exceeds 256 bytes")
        if type(item) is dict:
            for child in item.values():
                bounded_strings(child)
        elif type(item) is list:
            for child in item:
                bounded_strings(child)
    bounded_strings(value)
    if domain == "system":
        for key in ("cpu_ratio", "memory_ratio"):
            if value[key] is not None and not number(value[key], 0, 1):
                raise ValueError("invalid ratio")
        for key in ("temperature_c", "temperature_limit_c"):
            if value[key] is not None and not number(value[key], -50, 200):
                raise ValueError("invalid temperature")
        for key in ("psi_cpu", "psi_memory", "psi_io"):
            if value[key] is not None and not number(value[key], 0, 100):
                raise ValueError("invalid pressure")
        if type(value["sensor"]) is not str:
            raise ValueError("invalid sensor")
    elif domain == "storage":
        if type(value["mounts"]) is not list or len(value["mounts"]) > 16:
            raise ValueError("invalid mounts")
        for mount in value["mounts"]:
            if type(mount) is not dict or set(mount) != {"path", "available", "total", "ratio"}:
                raise ValueError("invalid mount")
            if type(mount["path"]) is not str or not number(mount["ratio"], 0, 1):
                raise ValueError("invalid mount ratio")
            if any(type(mount[k]) is not int or mount[k] < 0 for k in ("available", "total")):
                raise ValueError("invalid filesystem size")
            if mount["total"] == 0 or mount["available"] > mount["total"]:
                raise ValueError("inconsistent filesystem size")
    elif domain == "network":
        if type(value["interfaces"]) is not list or len(value["interfaces"]) > 64 or any(type(x) is not str or len(x.encode("utf-8")) > 64 for x in value["interfaces"]):
            raise ValueError("invalid interfaces")
        if value["default_route"] is not None and type(value["default_route"]) is not bool:
            raise ValueError("invalid route")
    elif domain == "media":
        if value["status"] not in ("playing", "paused", "stopped") or any(type(value[k]) is not str for k in ("player", "title", "artist")):
            raise ValueError("invalid media state")
    elif domain == "desktop":
        if any(type(value[k]) is not str for k in ("monitor", "workspace")) or type(value["fullscreen"]) is not bool:
            raise ValueError("invalid desktop state")
        if type(value["outputs"]) is not list or len(value["outputs"]) > 16 or any(type(x) is not str for x in value["outputs"]):
            raise ValueError("invalid outputs")
    elif domain == "session":
        if value["locked"] is not None and type(value["locked"]) is not bool:
            raise ValueError("invalid lock state")
    elif domain == "virtualization":
        if type(value["vms"]) is not list or len(value["vms"]) > 32:
            raise ValueError("invalid VMs")
        for vm in value["vms"]:
            if type(vm) is not dict or set(vm) != {"name", "state"} or any(type(v) is not str for v in vm.values()):
                raise ValueError("invalid VM")
            if len(vm["name"].encode("utf-8")) > 128 or len(vm["state"].encode("utf-8")) > 64:
                raise ValueError("invalid VM field size")


@dataclass(frozen=True)
class Rule:
    kind: str
    domain: str
    field: str
    enter: float
    leave: float
    dwell: float
    title: str
    unit: str
    severity: str = "warning"
    below: bool = False


RULES = (
    Rule("cpu", "system", "cpu_ratio", .90, .65, 12, "Carga de CPU sostenida", "%"),
    Rule("memory", "system", "memory_ratio", .90, .80, 12, "Memoria bajo presión", "%"),
    Rule("thermal", "system", "temperature_c", 85, 78, 4, "Temperatura elevada", "°C", "critical"),
)


class Model:
    def __init__(self, saved: dict | None = None, clock=time.monotonic, wall=time.time):
        self.clock, self.wall = clock, wall
        self.domains: dict[str, dict] = {}
        self.insights = copy.deepcopy((saved or {}).get("insights", {}))
        self.preferences = {"muted_until": 0, "reduced_motion": False, "avatar_visible": True,
                            "monitor": "", "margin_x": 32, "margin_y": 24,
                            **(saved or {}).get("preferences", {})}
        for item in self.insights.values():
            if item["status"] != "resolved":
                item["status"] = "unknown"
        self.candidates: dict[str, tuple[bool, float]] = {}
        self.revision = 0
        self.history = list((saved or {}).get("history", []))[-30:]
        self.health: dict[str, dict] = {}

    def fresh(self, domain: str) -> bool:
        item = self.domains.get(domain)
        return bool(item and self.clock() - item["monotonic"] <= LEASES[domain] and item["available"])

    def accept(self, domain: str, value: dict, sequence: int) -> list[dict]:
        validate_sample(domain, value)
        if not self.fresh(domain):
            self.candidates = {k: v for k, v in self.candidates.items() if not k.startswith(domain + ":")}
        self.domains[domain] = {"value": copy.deepcopy(value), "monotonic": self.clock(),
                                "updated_at": self.wall(), "sequence": sequence, "available": True}
        self.health[domain] = {"state": "healthy", "message": "Disponible"}
        self.revision += 1
        changes = []
        if domain == "system":
            thermal_key = f"system:thermal:{value['sensor'] or 'host'}"
            self.candidates = {k: v for k, v in self.candidates.items() if not k.startswith("system:thermal:") or k == thermal_key}
            for rule in RULES:
                enter, leave = rule.enter, rule.leave
                if rule.kind == "thermal" and value.get("temperature_limit_c") is not None:
                    enter = value["temperature_limit_c"]
                    leave = enter - 7
                subject = (value["sensor"] or "host") if rule.kind == "thermal" else "host"
                changes.extend(self._detect(rule, subject, value[rule.field], sequence, enter, leave))
        elif domain == "storage":
            for mount in value["mounts"]:
                rule = Rule("storage", "storage", "ratio", .10, .15, 0, "Poco espacio disponible", "% libre", below=True)
                changes.extend(self._detect(rule, mount["path"], mount["ratio"], sequence, .10, .15))
        elif domain == "network":
            rule = Rule("network", "network", "default_route", .5, .5, 6, "Sin ruta de salida", "", below=True)
            observed = value["default_route"]
            changes.extend(self._detect(rule, "host", None if observed is None else int(observed), sequence, .5, .5))
        subjects = {m["path"] for m in value["mounts"]} if domain == "storage" else {value["sensor"] or "host"} if domain == "system" else None
        for item in self.insights.values():
            if item["domain"] == domain and subjects is not None and (domain == "storage" or item["kind"] == "thermal") and item["subject"] not in subjects:
                self.candidates.pop(f"{domain}:{item['kind']}:{item['subject']}", None)
                if item["status"] == "active":
                    item["status"] = "unknown"
                    changes.append(self._record(item, "unknown"))
        while len(self.insights) > 24:
            oldest = min(self.insights.values(), key=lambda i: (i["status"] != "resolved", i["opened_at"]))
            del self.insights[oldest["id"]]
        return changes

    def _detect(self, rule: Rule, subject: str, value: Any, sequence: int, enter: float, leave: float) -> list[dict]:
        key = f"{rule.domain}:{rule.kind}:{subject}"
        ident = hashlib.sha256(key.encode()).hexdigest()[:16]
        existing = self.insights.get(ident)
        active = bool(existing and existing["status"] in ("active", "unknown"))
        if value is None:
            self.candidates.pop(key, None)
            if active and existing["status"] != "unknown":
                existing["status"] = "unknown"
                return [self._record(existing, "unknown")]
            return []
        bad = value <= enter if rule.below else value >= enter
        clear = value >= leave if rule.below else value <= leave
        target = True if bad else False if clear else None
        if existing:
            existing["latest_evidence"] = {"value": value, "unit": rule.unit, "threshold": enter,
                                    "subject": subject, "sequence": sequence, "observed_at": self.wall()}
            if existing["status"] == "unknown" and bad:
                existing["status"] = "active"
        if target is None or target == active:
            self.candidates.pop(key, None)
            return []
        if self.candidates.get(key, (None,))[0] != target:
            self.candidates[key] = (target, self.clock())
        duration = rule.dwell if target else 6
        if self.clock() - self.candidates[key][1] < duration:
            return []
        self.candidates.pop(key, None)
        if target:
            item = {"id": ident, "kind": rule.kind, "domain": rule.domain, "subject": subject,
                    "title": rule.title, "severity": rule.severity, "status": "active",
                    "opened_at": self.wall(), "updated_at": self.wall(), "acknowledged": False,
                    "snoozed_until": 0, "evidence": {"value": value, "unit": rule.unit,
                    "threshold": enter, "subject": subject, "sequence": sequence, "observed_at": self.wall()}}
            self.insights[ident] = item
            return [self._record(item, "active")]
        if existing:
            existing["status"] = "resolved"
            existing["updated_at"] = self.wall()
            return [self._record(existing, "resolved")]
        return []

    def _record(self, item: dict, status: str) -> dict:
        event = {"id": item["id"], "title": item["title"], "status": status,
                 "severity": item["severity"], "at": self.wall()}
        self.history = [event, *self.history][:30]
        return copy.deepcopy(event)

    def unavailable(self, domain: str, message: str) -> list[dict]:
        self.health[domain] = {"state": "unavailable", "message": message[:160]}
        if domain in self.domains:
            self.domains[domain]["available"] = False
        self.candidates = {k: v for k, v in self.candidates.items() if not k.startswith(domain + ":")}
        changes = []
        for item in self.insights.values():
            if item["domain"] == domain and item["status"] == "active":
                item["status"] = "unknown"
                changes.append(self._record(item, "unknown"))
        self.revision += 1
        return changes

    def expire(self) -> list[dict]:
        changes = []
        for domain, item in list(self.domains.items()):
            if item["available"] and not self.fresh(domain):
                changes.extend(self.unavailable(domain, "Sin lecturas recientes"))
        return changes

    def export(self) -> dict:
        return {"insights": self.insights, "preferences": self.preferences, "history": self.history}

    def snapshot(self) -> dict:
        domains = {key: {"value": copy.deepcopy(v["value"]), "fresh": self.fresh(key),
                    "age_s": round(max(0, self.clock()-v["monotonic"]), 1), "updated_at": v["updated_at"]}
                   for key, v in self.domains.items()}
        issues = sorted(self.insights.values(), key=lambda x: (x["status"] == "resolved", x["severity"] != "critical", -x["opened_at"]))[:32]
        active = [x for x in issues if x["status"] == "active"]
        media = domains.get("media", {})
        presence = "warning" if active else "unknown" if not self.fresh("system") else "media" if media.get("fresh") and media["value"]["status"] == "playing" else "idle"
        cpu = domains.get("system", {}).get("value", {}).get("cpu_ratio")
        if presence == "idle" and cpu is not None and cpu >= .70:
            presence = "busy"
        return {"version": "cc.status/1", "revision": self.revision, "domains": domains,
                "insights": copy.deepcopy(issues), "history": copy.deepcopy(self.history),
                "preferences": dict(self.preferences), "health": copy.deepcopy(self.health),
                "presence": presence, "time": self.wall()}

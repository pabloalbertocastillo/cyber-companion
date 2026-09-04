"""Compatibility ingress from the current v1 Event contract to Event v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from cyber_companion.events import Event

from .events import DeliveryClass, EventV2, PrivacyClass, RetentionClass


class CompatibilityError(ValueError):
    """Raised when a v1 event cannot be safely represented as a known v2 fact."""


@dataclass(frozen=True)
class _Rule:
    event_type: str
    source: str
    subject: str
    schema: str
    privacy: PrivacyClass
    delivery: DeliveryClass
    retention: RetentionClass
    ttl_ms: int | None
    allowed_fields: frozenset[str]


_SYSTEM_FIELDS = frozenset({"cpu_ratio", "memory_ratio", "temperature_c", "busy", "thermal_alert"})
_MEDIA_FIELDS = frozenset(
    {
        "status",
        "players",
        "active_players",
        "instance",
        "player",
        "track_id",
        "artist",
        "title",
        "changed_player",
    }
)
_ADAPTER_FIELDS = frozenset({"error", "returncode"})


_RULES: dict[tuple[str, str], _Rule] = {
    ("linux_system", "system.telemetry"): _Rule(
        "system.telemetry.sampled", "adapter://linux-system/local", "host/local",
        "cc.system.telemetry@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.LATEST_VALUE, RetentionClass.EPHEMERAL, 6000, _SYSTEM_FIELDS,
    ),
    ("linux_system", "system.busy"): _Rule(
        "system.busy.entered", "adapter://linux-system/local", "host/local",
        "cc.system.busy@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.ORDERED, RetentionClass.OPERATIONAL, None, _SYSTEM_FIELDS,
    ),
    ("linux_system", "system.idle"): _Rule(
        "system.busy.exited", "adapter://linux-system/local", "host/local",
        "cc.system.busy@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.ORDERED, RetentionClass.OPERATIONAL, None, _SYSTEM_FIELDS,
    ),
    ("mpris", "media.playing"): _Rule(
        "media.playback.started", "adapter://mpris/local", "media/local",
        "cc.media.playback@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.ORDERED, RetentionClass.OPERATIONAL, None, _MEDIA_FIELDS,
    ),
    ("mpris", "media.paused"): _Rule(
        "media.playback.paused", "adapter://mpris/local", "media/local",
        "cc.media.playback@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.ORDERED, RetentionClass.OPERATIONAL, None, _MEDIA_FIELDS,
    ),
    ("mpris", "media.stopped"): _Rule(
        "media.playback.stopped", "adapter://mpris/local", "media/local",
        "cc.media.playback@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.ORDERED, RetentionClass.OPERATIONAL, None, _MEDIA_FIELDS,
    ),
    ("mpris", "media.track_changed"): _Rule(
        "media.track.changed", "adapter://mpris/local", "media/local",
        "cc.media.track@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.ORDERED, RetentionClass.OPERATIONAL, None, _MEDIA_FIELDS,
    ),
    ("mpris", "media.updated"): _Rule(
        "media.playback.observed", "adapter://mpris/local", "media/local",
        "cc.media.playback@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.LATEST_VALUE, RetentionClass.EPHEMERAL, 10000, _MEDIA_FIELDS,
    ),
    ("mpris", "media.players_changed"): _Rule(
        "media.players.changed", "adapter://mpris/local", "media/local",
        "cc.media.playback@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.ORDERED, RetentionClass.OPERATIONAL, None, _MEDIA_FIELDS,
    ),
}

for _event_type in ("adapter.error", "adapter.invalid_data", "adapter.disconnected"):
    _RULES[("mpris", _event_type)] = _Rule(
        "component.health.changed", "adapter://mpris/local", "component/mpris",
        "cc.component.health@2", PrivacyClass.LOCAL_PRIVATE,
        DeliveryClass.ORDERED, RetentionClass.OPERATIONAL, None, _ADAPTER_FIELDS,
    )


class V1CompatibilityMapper:
    """Strict mapper for built-in v1 adapters.

    Unknown event identities and unknown payload keys are rejected rather than
    being silently merged into v2 state. Sequence allocation remains a Core v2
    ingress responsibility, so the caller supplies the accepted sequence.
    """

    def map(self, event: Event, *, sequence: int, observed_at: str | None = None) -> EventV2:
        if event.version != 1:
            raise CompatibilityError(f"expected v1 event, received version {event.version}")

        rule = _RULES.get((event.source, event.type))
        if rule is None:
            raise CompatibilityError(f"no v2 compatibility rule for {event.source}:{event.type}")

        data = dict(event.data)
        unknown = set(data) - rule.allowed_fields
        if unknown:
            fields = ", ".join(sorted(unknown))
            raise CompatibilityError(f"unknown fields for {event.source}:{event.type}: {fields}")

        return EventV2.create(
            event_type=rule.event_type,
            source=rule.source,
            subject=rule.subject,
            sequence=sequence,
            schema=rule.schema,
            data=data,
            privacy=rule.privacy,
            delivery=rule.delivery,
            retention=rule.retention,
            ttl_ms=rule.ttl_ms,
            occurred_at=event.timestamp,
            observed_at=observed_at,
        )

    def supports(self, source: str, event_type: str) -> bool:
        return (source, event_type) in _RULES

    def known_events(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(_RULES))

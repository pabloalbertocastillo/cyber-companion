"""Validated Event Envelope v2 contract.

The envelope is deliberately implemented with the Python standard library only.
Payload-schema validation belongs to the schema registry slice; this module owns
the invariant fields required before an event may enter Core v2.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping
from uuid import uuid4


SPECVERSION = "2.0"


class PrivacyClass(str, Enum):
    PUBLIC = "public"
    LOCAL = "local"
    LOCAL_PRIVATE = "local_private"
    SECRET = "secret"


class DeliveryClass(str, Enum):
    LATEST_VALUE = "latest_value"
    ORDERED = "ordered"
    CRITICAL = "critical"
    AUDIT = "audit"


class RetentionClass(str, Enum):
    EPHEMERAL = "ephemeral"
    OPERATIONAL = "operational"
    INCIDENT = "incident"
    CONVERSATION = "conversation"
    AUDIT = "audit"


def utc_now() -> str:
    """Return an RFC3339-like UTC timestamp with an explicit Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_event_id() -> str:
    """Return an opaque globally unique identifier.

    UUIDv4 is used until the persistence slice chooses whether sortable UUIDv7 or
    ULID identifiers provide a measurable benefit. Callers must treat IDs as
    opaque regardless of the implementation.
    """
    return f"evt_{uuid4().hex}"


def _require_nonempty(name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _validate_timestamp(name: str, value: str) -> None:
    _require_nonempty(name, value)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")


@dataclass(frozen=True)
class EventV2:
    specversion: str
    id: str
    type: str
    source: str
    subject: str
    occurred_at: str
    observed_at: str
    sequence: int
    correlation_id: str
    causation_id: str | None
    schema: str
    privacy: PrivacyClass
    delivery: DeliveryClass
    retention: RetentionClass
    ttl_ms: int | None
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.specversion != SPECVERSION:
            raise ValueError(f"unsupported event specversion: {self.specversion!r}")
        for name in ("id", "type", "source", "subject", "correlation_id", "schema"):
            _require_nonempty(name, getattr(self, name))
        _validate_timestamp("occurred_at", self.occurred_at)
        _validate_timestamp("observed_at", self.observed_at)
        if self.sequence < 1:
            raise ValueError("sequence must be >= 1")
        if self.causation_id is not None:
            _require_nonempty("causation_id", self.causation_id)
        if self.ttl_ms is not None and self.ttl_ms <= 0:
            raise ValueError("ttl_ms must be positive when present")
        if not isinstance(self.data, Mapping):
            raise TypeError("data must be a mapping")

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        source: str,
        subject: str,
        sequence: int,
        schema: str,
        data: Mapping[str, object],
        privacy: PrivacyClass,
        delivery: DeliveryClass,
        retention: RetentionClass,
        ttl_ms: int | None = None,
        occurred_at: str | None = None,
        observed_at: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        event_id: str | None = None,
    ) -> "EventV2":
        accepted_at = observed_at or utc_now()
        return cls(
            specversion=SPECVERSION,
            id=event_id or new_event_id(),
            type=event_type,
            source=source,
            subject=subject,
            occurred_at=occurred_at or accepted_at,
            observed_at=accepted_at,
            sequence=sequence,
            correlation_id=correlation_id or f"corr_{uuid4().hex}",
            causation_id=causation_id,
            schema=schema,
            privacy=privacy,
            delivery=delivery,
            retention=retention,
            ttl_ms=ttl_ms,
            data=dict(data),
        )

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["privacy"] = self.privacy.value
        result["delivery"] = self.delivery.value
        result["retention"] = self.retention.value
        return result

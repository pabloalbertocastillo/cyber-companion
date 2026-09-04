"""Core v2 contracts.

This package is intentionally independent from the v0.11 runtime so migration can
proceed behind compatibility adapters without changing visible Wisp behavior.
"""

from .events import (
    DeliveryClass,
    EventV2,
    PrivacyClass,
    RetentionClass,
    new_event_id,
    utc_now,
)
from .compat_v1 import CompatibilityError, V1CompatibilityMapper

__all__ = [
    "CompatibilityError",
    "DeliveryClass",
    "EventV2",
    "PrivacyClass",
    "RetentionClass",
    "V1CompatibilityMapper",
    "new_event_id",
    "utc_now",
]

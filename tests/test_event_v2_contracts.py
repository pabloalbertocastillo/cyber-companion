import unittest

from cyber_companion.core.compat_v1 import CompatibilityError, V1CompatibilityMapper
from cyber_companion.core.events import (
    DeliveryClass,
    EventV2,
    PrivacyClass,
    RetentionClass,
)
from cyber_companion.events import Event


class EventV2ContractTests(unittest.TestCase):
    def test_create_serializes_closed_classifications(self) -> None:
        event = EventV2.create(
            event_type="system.telemetry.sampled",
            source="adapter://linux-system/local",
            subject="host/local",
            sequence=7,
            schema="cc.system.telemetry@2",
            data={"cpu_ratio": 0.42},
            privacy=PrivacyClass.LOCAL_PRIVATE,
            delivery=DeliveryClass.LATEST_VALUE,
            retention=RetentionClass.EPHEMERAL,
            ttl_ms=6000,
            observed_at="2026-09-04T18:15:02.156Z",
        )

        serialized = event.as_dict()
        self.assertEqual(serialized["specversion"], "2.0")
        self.assertTrue(str(serialized["id"]).startswith("evt_"))
        self.assertEqual(serialized["sequence"], 7)
        self.assertEqual(serialized["privacy"], "local_private")
        self.assertEqual(serialized["delivery"], "latest_value")
        self.assertEqual(serialized["retention"], "ephemeral")

    def test_rejects_invalid_sequence_ttl_and_naive_time(self) -> None:
        common = dict(
            event_type="system.telemetry.sampled",
            source="adapter://linux-system/local",
            subject="host/local",
            schema="cc.system.telemetry@2",
            data={},
            privacy=PrivacyClass.LOCAL,
            delivery=DeliveryClass.LATEST_VALUE,
            retention=RetentionClass.EPHEMERAL,
        )
        with self.assertRaises(ValueError):
            EventV2.create(sequence=0, **common)
        with self.assertRaises(ValueError):
            EventV2.create(sequence=1, ttl_ms=0, **common)
        with self.assertRaises(ValueError):
            EventV2.create(sequence=1, occurred_at="2026-09-04T18:15:02", **common)


class CompatibilityMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapper = V1CompatibilityMapper()

    def test_maps_system_telemetry_without_mutating_v1(self) -> None:
        source = Event(
            version=1,
            source="linux_system",
            type="system.telemetry",
            timestamp="2026-09-04T18:15:02+00:00",
            data={
                "cpu_ratio": 0.83,
                "memory_ratio": 0.41,
                "temperature_c": 67.0,
                "busy": True,
                "thermal_alert": False,
            },
        )
        mapped = self.mapper.map(
            source,
            sequence=4812,
            observed_at="2026-09-04T18:15:02.156Z",
        )

        self.assertEqual(mapped.type, "system.telemetry.sampled")
        self.assertEqual(mapped.source, "adapter://linux-system/local")
        self.assertEqual(mapped.subject, "host/local")
        self.assertEqual(mapped.schema, "cc.system.telemetry@2")
        self.assertEqual(mapped.delivery, DeliveryClass.LATEST_VALUE)
        self.assertEqual(mapped.ttl_ms, 6000)
        self.assertEqual(mapped.occurred_at, source.timestamp)
        self.assertEqual(mapped.sequence, 4812)
        self.assertEqual(source.type, "system.telemetry")

    def test_maps_current_media_transition(self) -> None:
        source = Event(
            version=1,
            source="mpris",
            type="media.playing",
            timestamp="2026-09-04T18:15:02+00:00",
            data={"status": "playing", "players": [], "active_players": []},
        )
        mapped = self.mapper.map(source, sequence=2)
        self.assertEqual(mapped.type, "media.playback.started")
        self.assertEqual(mapped.delivery, DeliveryClass.ORDERED)
        self.assertEqual(mapped.retention, RetentionClass.OPERATIONAL)

    def test_rejects_unknown_event_and_unknown_payload_field(self) -> None:
        unsupported = Event(
            version=1,
            source="unknown",
            type="something.happened",
            timestamp="2026-09-04T18:15:02+00:00",
            data={},
        )
        with self.assertRaises(CompatibilityError):
            self.mapper.map(unsupported, sequence=1)

        unsafe = Event(
            version=1,
            source="linux_system",
            type="system.telemetry",
            timestamp="2026-09-04T18:15:02+00:00",
            data={"cpu_ratio": 0.2, "surprise": "must-not-pass"},
        )
        with self.assertRaises(CompatibilityError):
            self.mapper.map(unsafe, sequence=1)

    def test_all_current_builtin_event_identities_are_declared(self) -> None:
        expected = {
            ("linux_system", "system.telemetry"),
            ("linux_system", "system.busy"),
            ("linux_system", "system.idle"),
            ("mpris", "media.playing"),
            ("mpris", "media.paused"),
            ("mpris", "media.stopped"),
            ("mpris", "media.track_changed"),
            ("mpris", "media.updated"),
            ("mpris", "media.players_changed"),
            ("mpris", "adapter.error"),
            ("mpris", "adapter.invalid_data"),
            ("mpris", "adapter.disconnected"),
        }
        self.assertEqual(set(self.mapper.known_events()), expected)


if __name__ == "__main__":
    unittest.main()

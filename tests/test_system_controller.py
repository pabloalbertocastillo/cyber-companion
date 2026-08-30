import json
import tempfile
import unittest
from pathlib import Path

from cyber_companion.behavior import BehaviorEngine, BehaviorRule, load_behavior_engine
from cyber_companion.director import BehaviorDirector
from cyber_companion.adapters.mpris import (
    FIELD_SEPARATOR,
    MprisEventMapper,
    PlayerctlMprisAdapter,
    parse_playerctl_line,
)
from cyber_companion.adapters.registry import build_adapters, load_adapter_specs
from cyber_companion.adapters.system import BusyLatch, cpu_ratio, read_memory_ratio, read_temperature_c
from cyber_companion.events import Event
from cyber_companion.presentation import PresentationCommand
from cyber_companion.renderers.media_signals import MediaSignalRendererAdapter
from cyber_companion.state import StateStore


class MprisTests(unittest.TestCase):
    def test_parse_spotify_metadata(self) -> None:
        line = FIELD_SEPARATOR.join(("spotify", "spotify", "Playing", "/track/7", "Example Artist", "Example Track")) + "\n"
        snapshot = parse_playerctl_line(line)
        assert snapshot is not None
        self.assertEqual(snapshot.status, "playing")
        self.assertEqual(snapshot.artist, "Example Artist")
        self.assertEqual(snapshot.title, "Example Track")

    def test_mapper_emits_track_and_status_only_when_changed(self) -> None:
        mapper = MprisEventMapper()
        first = FIELD_SEPARATOR.join(("spotify", "spotify", "Playing", "/track/1", "Artist", "One")) + "\n"
        second = FIELD_SEPARATOR.join(("spotify", "spotify", "Playing", "/track/2", "Artist", "Two")) + "\n"

        self.assertEqual([event.type for event in mapper.events_for_line(first)], ["media.track_changed", "media.playing"])
        self.assertEqual(mapper.events_for_line(first), [])
        self.assertEqual([event.type for event in mapper.events_for_line(second)], ["media.track_changed"])
        self.assertEqual([event.type for event in mapper.stopped_events()], ["media.stopped"])

    def test_invalid_status_is_rejected(self) -> None:
        line = FIELD_SEPARATOR.join(("spotify", "spotify", "Buffering", "", "", ""))
        with self.assertRaises(ValueError):
            parse_playerctl_line(line)

    def test_multiple_players_keep_media_active(self) -> None:
        mapper = MprisEventMapper()
        spotify = FIELD_SEPARATOR.join(("spotify", "spotify", "Playing", "/track/1", "Artist", "Song")) + "\n"
        youtube = FIELD_SEPARATOR.join(("firefox.instance1", "firefox", "Playing", "/video/1", "", "Video")) + "\n"
        spotify_paused = FIELD_SEPARATOR.join(("spotify", "spotify", "Paused", "/track/1", "Artist", "Song")) + "\n"

        mapper.events_for_line(spotify)
        mapper.events_for_line(youtube)
        events = mapper.events_for_line(spotify_paused)

        self.assertNotIn("media.paused", [event.type for event in events])

    def test_adapter_follows_all_players(self) -> None:
        command = PlayerctlMprisAdapter().command()
        self.assertIn("--all-players", command)
        self.assertNotIn("--player=spotify", command)

    def test_adapter_registry_is_configuration_driven(self) -> None:
        root = Path(__file__).resolve().parents[1]
        specs = load_adapter_specs(root / "config/adapters.json")
        adapters = build_adapters(specs)
        self.assertEqual([name for name, _adapter in adapters], ["desktop_media", "gentoo_system"])
        self.assertIsInstance(adapters[0][1], PlayerctlMprisAdapter)

    def test_unknown_enabled_adapter_is_rejected(self) -> None:
        from cyber_companion.adapters.registry import AdapterSpec

        with self.assertRaisesRegex(ValueError, "unknown enabled adapter type"):
            build_adapters([AdapterSpec("future", "missing", True, {})])


class StateAndRendererTests(unittest.TestCase):
    def test_custom_sprite_config_is_ordered_without_spurious_warnings(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = (root / "config/wpets.conf.example").read_text(encoding="utf-8")
        lines = config.splitlines()
        self.assertLess(
            lines.index("custom_sprite_sheet_filename=assets/sprites/companion-wisp-system-v0.11.png"),
            lines.index("animation_name=custom"),
        )
        self.assertIn("happy_kpm=0", lines)
        validation_patch = (root / "renderer/patches/0003-happy-kpm-validation.patch").read_text(encoding="utf-8")
        self.assertIn("config.happy_kpm > 0", validation_patch)

    def test_state_switches_profiles_and_persists_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            presentations: list[str] = []
            store = StateStore(
                state_path=state_path,
                initial_presentation=PresentationCommand("idle", "system_presence", 0.25),
            )
            store.initialize()
            store.handle(
                Event.create(
                    "mpris",
                    "media.playing",
                    {"player": "spotify", "status": "playing", "title": "Example Track", "artist": "Example Artist"},
                )
            )

            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(presentations, [])
            self.assertEqual(persisted["presentation"]["profile"], "idle")
            self.assertEqual(persisted["media"]["title"], "Example Track")
            self.assertEqual(persisted["domains"]["media"]["status"], "playing")

    def test_renderer_sends_native_media_signals_once_per_profile(self) -> None:
        notified: list[tuple[int, int]] = []
        renderer = MediaSignalRendererAdapter(
            renderer_pid=123,
            profiles={"idle", "media", "system_busy"},
            notifier=lambda process_id, signal_number: notified.append((process_id, signal_number)),
        )

        idle = PresentationCommand("idle", "system_presence", 0.25)
        media = PresentationCommand("media", "music_sway", 0.65)
        self.assertTrue(renderer.apply(idle))
        self.assertFalse(renderer.apply(idle))
        self.assertTrue(renderer.apply(media))
        self.assertEqual(len(notified), 2)
        self.assertEqual(notified[0][0], 123)
        self.assertEqual(notified[1][0], 123)
        self.assertEqual(notified[1][1], notified[0][1] - 1)

        busy = PresentationCommand("system_busy", "processing", 0.75)
        self.assertTrue(renderer.apply(busy))
        self.assertEqual(notified[2][1], notified[0][1] + 1)

    def test_reconciliation_removes_closed_playing_player(self) -> None:
        mapper = MprisEventMapper()
        spotify = parse_playerctl_line(
            FIELD_SEPARATOR.join(("spotify", "spotify", "Playing", "/track/1", "Artist", "Song"))
        )
        browser = parse_playerctl_line(
            FIELD_SEPARATOR.join(("firefox.instance1", "firefox", "Paused", "/video/1", "", "Video"))
        )
        assert spotify is not None and browser is not None
        mapper.events_for_snapshots([spotify, browser])

        events = mapper.events_for_snapshots([browser])

        self.assertIn("media.paused", [event.type for event in events])

    def test_behavior_config_is_declarative_and_resolves_media(self) -> None:
        root = Path(__file__).resolve().parents[1]
        engine = load_behavior_engine(root / "config/behaviors.json")
        idle = engine.resolve({"domains": {}})
        media = engine.resolve({"domains": {"media": {"status": "playing"}}})
        self.assertEqual(idle.behavior, "system_presence")
        self.assertEqual(media.behavior, "music_sway")
        self.assertEqual(media.profile, "media")

        busy = engine.resolve({"domains": {"system": {"busy": True}, "media": {"status": "playing"}}})
        self.assertEqual(busy.behavior, "processing")
        self.assertEqual(busy.profile, "system_busy")

    def test_behavior_priority_is_deterministic(self) -> None:
        default = PresentationCommand("idle", "idle")
        low = BehaviorRule("low", 10, "domains.system.alert", True, PresentationCommand("media", "low"))
        high = BehaviorRule("high", 100, "domains.system.alert", True, PresentationCommand("idle", "high"))
        engine = BehaviorEngine(default, [low, high])
        self.assertEqual(engine.resolve({"domains": {"system": {"alert": True}}}).behavior, "high")

    def test_director_is_single_presentation_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            default = PresentationCommand("idle", "system_presence", 0.25)
            media = PresentationCommand("media", "music_sway", 0.65)
            engine = BehaviorEngine(default, [BehaviorRule("media", 40, "domains.media.status", "playing", media)])
            state = StateStore(Path(directory) / "state.json", default)

            class Renderer:
                def __init__(self) -> None:
                    self.commands: list[PresentationCommand] = []

                def apply(self, command: PresentationCommand) -> None:
                    self.commands.append(command)

            renderer = Renderer()
            director = BehaviorDirector(state, engine, renderer)
            director.initialize()
            event = Event.create("mpris", "media.playing", {"status": "playing"})
            director.handle(event)
            director.handle(event)
            director.handle(Event.create("mpris", "media.paused", {"status": "paused"}))
            self.assertEqual([command.profile for command in renderer.commands], ["media", "idle"])

    def test_autonomous_renderer_movement_is_disabled(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = (root / "config/wpets.conf.example").read_text(encoding="utf-8")
        self.assertIn("movement_radius=0", config.splitlines())
        self.assertIn("movement_speed=0", config.splitlines())


class SystemAdapterTests(unittest.TestCase):
    def test_cpu_ratio_uses_jiffy_deltas(self) -> None:
        self.assertAlmostEqual(cpu_ratio((100, 40), (200, 70)), 0.70)
        self.assertEqual(cpu_ratio((100, 40), (100, 40)), 0.0)

    def test_busy_latch_requires_sustained_thresholds(self) -> None:
        now = [0.0]
        latch = BusyLatch(0.70, 4.0, 0.40, 6.0, clock=lambda: now[0])
        self.assertFalse(latch.update(0.80))
        now[0] = 3.9
        self.assertFalse(latch.update(0.80))
        now[0] = 4.0
        self.assertTrue(latch.update(0.80))
        now[0] = 9.0
        self.assertTrue(latch.update(0.30))
        now[0] = 15.0
        self.assertFalse(latch.update(0.30))

    def test_memory_and_temperature_readers_tolerate_realistic_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "meminfo"
            memory.write_text("MemTotal: 1000 kB\nMemAvailable: 250 kB\n", encoding="utf-8")
            self.assertEqual(read_memory_ratio(memory), 0.75)

            hwmon = root / "hwmon0"
            hwmon.mkdir()
            (hwmon / "temp1_input").write_text("52000\n", encoding="utf-8")
            (hwmon / "temp2_input").write_text("not-a-number\n", encoding="utf-8")
            self.assertEqual(read_temperature_c(root), 52.0)


if __name__ == "__main__":
    unittest.main()

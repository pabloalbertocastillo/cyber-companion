import json
import tempfile
import unittest
from pathlib import Path

from cyber_companion.adapters.mpris import (
    FIELD_SEPARATOR,
    MprisEventMapper,
    PlayerctlMprisAdapter,
    parse_playerctl_line,
)
from cyber_companion.events import Event
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


class StateAndRendererTests(unittest.TestCase):
    def test_custom_sprite_config_is_ordered_without_spurious_warnings(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = (root / "config/wpets.conf.example").read_text(encoding="utf-8")
        lines = config.splitlines()
        self.assertLess(
            lines.index("custom_sprite_sheet_filename=assets/sprites/companion-wisp-system-v0.9.png"),
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
                default_profile="idle",
                event_profiles={"media.playing": "media", "media.paused": "idle"},
                on_presentation=presentations.append,
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
            self.assertEqual(presentations, ["idle", "media"])
            self.assertEqual(persisted["presentation"]["profile"], "media")
            self.assertEqual(persisted["media"]["title"], "Example Track")

    def test_renderer_sends_native_media_signals_once_per_profile(self) -> None:
        notified: list[tuple[int, int]] = []
        renderer = MediaSignalRendererAdapter(
            renderer_pid=123,
            profiles={"idle", "media"},
            notifier=lambda process_id, signal_number: notified.append((process_id, signal_number)),
        )

        self.assertTrue(renderer.apply("idle"))
        self.assertFalse(renderer.apply("idle"))
        self.assertTrue(renderer.apply("media"))
        self.assertEqual(len(notified), 2)
        self.assertEqual(notified[0][0], 123)
        self.assertEqual(notified[1][0], 123)
        self.assertEqual(notified[1][1], notified[0][1] - 1)

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


if __name__ == "__main__":
    unittest.main()

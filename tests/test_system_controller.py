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
from cyber_companion.renderers.wpets import WpetsRendererAdapter, render_config
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

    def test_render_config_replaces_only_known_values(self) -> None:
        base = "# comment\nanimation_speed=42\nmovement_wait_factor=18.0\n"
        rendered = render_config(base, {"animation_speed": 34, "movement_wait_factor": 3.0})
        self.assertEqual(rendered, "# comment\nanimation_speed=34\nmovement_wait_factor=3.0\n")

    def test_render_config_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ValueError):
            render_config("animation_speed=42\n", {"missing": 1})

    def test_renderer_notifies_once_per_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.conf"
            runtime = root / "runtime.conf"
            base.write_text("animation_speed=42\nmovement_wait_factor=18.0\n", encoding="utf-8")
            notified: list[int] = []
            renderer = WpetsRendererAdapter(
                base_config_path=base,
                runtime_config_path=runtime,
                profiles={
                    "idle": {"wpets": {"animation_speed": 42, "movement_wait_factor": 18.0}},
                    "media": {"wpets": {"animation_speed": 34, "movement_wait_factor": 3.0}},
                },
                renderer_pid=123,
                notifier=notified.append,
            )

            self.assertTrue(renderer.apply("idle"))
            self.assertFalse(renderer.apply("idle"))
            self.assertTrue(renderer.apply("media"))
            self.assertEqual(notified, [123, 123])
            self.assertIn("animation_speed=34", runtime.read_text(encoding="utf-8"))

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

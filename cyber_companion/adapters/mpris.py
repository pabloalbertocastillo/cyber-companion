"""MPRIS events supplied by playerctl's official follow mode."""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass

from cyber_companion.events import Event, EventBus


FIELD_SEPARATOR = "\x1f"
PLAYERCTL_FORMAT = FIELD_SEPARATOR.join(
    ("{{playerInstance}}", "{{playerName}}", "{{status}}", "{{mpris:trackid}}", "{{artist}}", "{{title}}")
)


@dataclass(frozen=True)
class PlayerSnapshot:
    instance: str
    player: str
    status: str
    track_id: str
    artist: str
    title: str

    def as_data(self) -> dict[str, object]:
        return {
            "instance": self.instance,
            "player": self.player,
            "status": self.status,
            "track_id": self.track_id,
            "artist": self.artist,
            "title": self.title,
        }


def parse_playerctl_line(line: str) -> PlayerSnapshot | None:
    stripped = line.rstrip("\r\n")
    if not stripped:
        return None

    fields = stripped.split(FIELD_SEPARATOR)
    if len(fields) != 6:
        raise ValueError(f"expected six MPRIS fields, received {len(fields)}")

    instance, player, status, track_id, artist, title = fields
    normalized_status = status.strip().lower()
    if normalized_status not in {"playing", "paused", "stopped"}:
        raise ValueError(f"unsupported MPRIS playback status: {status!r}")

    return PlayerSnapshot(
        instance=instance,
        player=player or instance,
        status=normalized_status,
        track_id=track_id,
        artist=artist,
        title=title,
    )


class MprisEventMapper:
    def __init__(self) -> None:
        self._players: dict[str, PlayerSnapshot] = {}
        self._aggregate_status = "stopped"

    def _aggregate_data(self, changed: PlayerSnapshot | None = None) -> dict[str, object]:
        players = sorted(self._players.values(), key=lambda snapshot: snapshot.instance)
        playing = [snapshot for snapshot in players if snapshot.status == "playing"]
        paused = [snapshot for snapshot in players if snapshot.status == "paused"]
        primary = playing[0] if playing else paused[0] if paused else changed
        data: dict[str, object] = {
            "status": "playing" if playing else "paused" if paused else "stopped",
            "players": [snapshot.as_data() for snapshot in players],
            "active_players": [snapshot.as_data() for snapshot in playing],
        }
        if primary is not None:
            data.update(primary.as_data())
            data["status"] = "playing" if playing else "paused" if paused else "stopped"
        return data

    def events_for_line(self, line: str) -> list[Event]:
        snapshot = parse_playerctl_line(line)
        if snapshot is None:
            return self.events_for_snapshots([])

        previous = self._players.get(snapshot.instance)
        previous_instances = set(self._players)
        self._players[snapshot.instance] = snapshot
        events: list[Event] = []

        if snapshot.track_id and (previous is None or snapshot.track_id != previous.track_id):
            track_data = self._aggregate_data(snapshot)
            track_data["changed_player"] = snapshot.as_data()
            events.append(Event.create("mpris", "media.track_changed", track_data))

        aggregate_data = self._aggregate_data(snapshot)
        aggregate_status = str(aggregate_data["status"])
        if aggregate_status != self._aggregate_status:
            events.append(Event.create("mpris", f"media.{aggregate_status}", aggregate_data))

        if not events and (previous != snapshot or previous_instances != set(self._players)):
            events.append(Event.create("mpris", "media.updated", aggregate_data))

        self._aggregate_status = aggregate_status
        return events

    def events_for_snapshots(self, snapshots: list[PlayerSnapshot]) -> list[Event]:
        previous_players = self._players
        next_players = {snapshot.instance: snapshot for snapshot in snapshots}
        self._players = next_players
        events: list[Event] = []

        for instance, snapshot in sorted(next_players.items()):
            previous = previous_players.get(instance)
            if snapshot.track_id and (previous is None or snapshot.track_id != previous.track_id):
                track_data = self._aggregate_data(snapshot)
                track_data["changed_player"] = snapshot.as_data()
                events.append(Event.create("mpris", "media.track_changed", track_data))

        aggregate_data = self._aggregate_data()
        aggregate_status = str(aggregate_data["status"])
        if aggregate_status != self._aggregate_status:
            events.append(Event.create("mpris", f"media.{aggregate_status}", aggregate_data))

        if not events and previous_players != next_players:
            events.append(Event.create("mpris", "media.players_changed", aggregate_data))

        self._aggregate_status = aggregate_status
        return events

    def stopped_events(self) -> list[Event]:
        return self.events_for_line("")


class PlayerctlMprisAdapter:
    def __init__(self, executable: str = "playerctl") -> None:
        self.executable = executable
        self.mapper = MprisEventMapper()
        self._process: subprocess.Popen[str] | None = None
        self._mapper_lock = threading.Lock()

    def command(self) -> list[str]:
        return [
            self.executable,
            "--no-messages",
            "--all-players",
            "--follow",
            "metadata",
            "--format",
            PLAYERCTL_FORMAT,
        ]

    def snapshot_command(self) -> list[str]:
        return [
            self.executable,
            "--no-messages",
            "--all-players",
            "metadata",
            "--format",
            PLAYERCTL_FORMAT,
        ]

    def _publish_follow_line(self, bus: EventBus, line: str) -> None:
        with self._mapper_lock:
            events = self.mapper.events_for_line(line)
        for event in events:
            bus.publish(event)

    def _reconcile(self, bus: EventBus) -> None:
        try:
            result = subprocess.run(
                self.snapshot_command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3.0,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return

        snapshots: list[PlayerSnapshot] = []
        for line in result.stdout.splitlines():
            try:
                snapshot = parse_playerctl_line(line)
            except ValueError:
                continue
            if snapshot is not None:
                snapshots.append(snapshot)

        with self._mapper_lock:
            events = self.mapper.events_for_snapshots(snapshots)
        for event in events:
            bus.publish(event)

    def _reconcile_loop(
        self,
        bus: EventBus,
        stop_event: threading.Event,
        reconcile_stop: threading.Event,
    ) -> None:
        while not stop_event.is_set() and not reconcile_stop.is_set():
            self._reconcile(bus)
            reconcile_stop.wait(5.0)

    def stop(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    def run(self, bus: EventBus, stop_event: threading.Event) -> None:
        reconcile_stop = threading.Event()
        reconcile_thread: threading.Thread | None = None
        try:
            while not stop_event.is_set():
                try:
                    process_context = subprocess.Popen(
                        self.command(),
                        stdout=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                    )
                except FileNotFoundError:
                    bus.publish(
                        Event.create(
                            "mpris",
                            "adapter.error",
                            {"error": f"executable not found: {self.executable}"},
                        )
                    )
                    return

                if reconcile_thread is None:
                    reconcile_thread = threading.Thread(
                        target=self._reconcile_loop,
                        args=(bus, stop_event, reconcile_stop),
                        name="mpris-reconcile",
                        daemon=True,
                    )
                    reconcile_thread.start()

                process = process_context
                self._process = process
                try:
                    assert process.stdout is not None
                    for line in process.stdout:
                        if stop_event.is_set():
                            break
                        try:
                            self._publish_follow_line(bus, line)
                        except ValueError as error:
                            bus.publish(Event.create("mpris", "adapter.invalid_data", {"error": str(error)}))

                    if not stop_event.is_set():
                        bus.publish(
                            Event.create(
                                "mpris",
                                "adapter.disconnected",
                                {"returncode": process.wait()},
                            )
                        )
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=2.0)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                    if process.stdout is not None:
                        process.stdout.close()
                    self._process = None

                stop_event.wait(1.0)
        finally:
            reconcile_stop.set()
            if reconcile_thread is not None:
                reconcile_thread.join(timeout=4.0)

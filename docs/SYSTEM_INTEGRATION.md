# System integration v0.11

v0.11 retains all-player MPRIS and adds dependency-free Linux telemetry. Both
adapters emit normalized events and select behavior without granting the
renderer access to D-Bus, `/proc` or `hwmon`.

```text
Spotify, browsers, VLC, mpv ... -> MPRIS -> playerctl --all-players --follow
                                             -> event bus -> domain state
                                                          -> behavior director
                                                          -> native media signal

/proc + hwmon -> linux_system adapter -> event bus -> domain state
                                                   -> behavior director
                                                   -> native system signal
```

## Runtime behavior

| Media state | Profile | Visible behavior |
|---|---|---|
| Any player playing | `media` | Activation, upright arm dance, then a continuous rhythmic loop |
| Paused, stopped or absent | `idle` | Deactivation and exact return to calm breathing |
| Track changed | unchanged | Metadata is updated without restarting the animation |
| CPU ≥70% for 4s | `system_busy` | Upright processing activation and loop |
| CPU ≤40% for 6s | next eligible | Smooth processing exit |
| Temperature ≥80°C | `system_busy` | Highest-priority thermal behavior |

Behavior selection is configured in `config/behaviors.json`. MPRIS only emits
normalized events; it never selects renderer signals or animation rows. The
behavior director is the single presentation authority.

The controller writes only to:

```text
$XDG_RUNTIME_DIR/cyber-companion/state.json
```

The file is user-private and disappears with the login session. Configuration
is never rewritten or reloaded during playback. The pinned renderer patch
reserves `SIGRTMIN` for media start and `SIGRTMIN+1` for media stop; both update
an independent `media_active` state and trigger the existing
`StartWorking → Working → EndWorking` animation path.

This avoids resetting the whole animation state machine on each play/pause
event. Autonomous renderer travel is disabled with `movement_radius=0` and
`movement_speed=0`, so it cannot compete with director-owned behavior. CPU state
remains independent for a future system-load reaction.

This milestone covers applications that implement MPRIS. Browser media such as
YouTube normally participates through the browser's MPRIS integration, as do
Spotify, VLC and suitably configured mpv. Raw PipeWire audio streams from games
or applications without MPRIS will require a separate audio-activity adapter;
they are intentionally not inferred from volume alone in v0.11.

## Interactive test

```bash
CYBER_COMPANION_MONITOR=<monitor-name> ./scripts/run-system.sh
```

While it runs, alternate Spotify, YouTube or another MPRIS player between play
and pause. Wisp must remain upright and visibly move both arms. If several
players exist, Wisp remains in `media` while at least one is playing. Inspect
normalized state with:

```bash
python3 -m json.tool "$XDG_RUNTIME_DIR/cyber-companion/state.json"
```

Stop the foreground launcher with `Ctrl+C`. Hyprland autostart remains deferred
until this transition test is accepted.

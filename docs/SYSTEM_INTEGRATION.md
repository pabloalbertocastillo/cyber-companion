# System integration v0.8

v0.8 is the first end-to-end system connection. It listens to every available
MPRIS source, normalizes media events and selects a presentation profile without
granting the renderer access to D-Bus.

```text
Spotify, browsers, VLC, mpv ... -> MPRIS -> playerctl --all-players --follow
                                             -> event bus -> state store
                                                          -> wpets adapter
```

## Runtime behavior

| Media state | Profile | Visible behavior |
|---|---|---|
| Any player playing | `media` | Faster energy cycle and more frequent autonomous flight |
| Paused, stopped or absent | `idle` | Approved v0.7 calm behavior |
| Track changed | unchanged | Metadata is updated without restarting the animation |

The adapter writes only to:

```text
$XDG_RUNTIME_DIR/cyber-companion/wpets.conf
$XDG_RUNTIME_DIR/cyber-companion/state.json
```

Both files are user-private and disappear with the login session. The
versioned example configuration remains untouched. Runtime configuration is
written atomically and the renderer is notified through its documented
`SIGUSR2` reload path.

This milestone covers applications that implement MPRIS. Browser media such as
YouTube normally participates through the browser's MPRIS integration, as do
Spotify, VLC and suitably configured mpv. Raw PipeWire audio streams from games
or applications without MPRIS will require a separate audio-activity adapter;
they are intentionally not inferred from volume alone in v0.8.

## Interactive test

```bash
CYBER_COMPANION_MONITOR=<monitor-name> ./scripts/run-system.sh
```

While it runs, alternate Spotify, YouTube or another MPRIS player between play
and pause. If several players exist, Wisp remains in `media` while at least one
is playing. Inspect normalized state with:

```bash
python3 -m json.tool "$XDG_RUNTIME_DIR/cyber-companion/state.json"
```

Stop the foreground launcher with `Ctrl+C`. Hyprland autostart remains deferred
until this transition test is accepted.

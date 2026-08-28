# Architecture

Cyber Companion separates system observation, behavior and rendering.

```text
system adapters -> normalized events -> state engine -> presentation command
                                                    -> renderer adapter
```

## Event envelope

Every integration should emit a small normalized event instead of controlling
the avatar directly.

```json
{
  "version": 1,
  "source": "mpris",
  "type": "media.playing",
  "timestamp": "2026-08-25T12:00:00-06:00",
  "data": {
    "title": "Example track",
    "artist": "Example artist"
  }
}
```

Initial event families:

| Source | Events |
|---|---|
| MPRIS | `media.playing`, `media.paused`, `media.stopped` |
| libvirt | `vm.starting`, `vm.running`, `vm.stopping`, `vm.off` |
| network | `network.online`, `network.offline` |
| system | `system.busy`, `system.thermal_alert`, `system.idle` |
| session | `session.locked`, `session.active`, `session.shutdown` |
| AI (future) | `ai.listening`, `ai.thinking`, `ai.speaking`, `ai.error` |

## Presentation command

The state engine resolves competing events into one presentation command:

```json
{
  "form": "wisp",
  "emotion": "enjoying_music",
  "animation": "music_sway",
  "accent": "cyan",
  "intensity": 0.65,
  "ttl_ms": 12000
}
```

Priority order for the first implementation:

1. Critical thermal or system errors
2. Session shutdown or lock
3. VM transitions and network loss
4. Direct interaction
5. Music
6. Idle

## Renderer contract

A renderer adapter receives presentation commands. It must not query MPRIS,
libvirt or system state itself. This permits several implementations:

- Wayland V-Pets sprite sheets for the first prototype.
- A custom `wlr-layer-shell` renderer if more control is required.
- Live2D or another GPU renderer later.

## Runtime locations

```text
$XDG_CONFIG_HOME/cyber-companion/   User configuration
$XDG_STATE_HOME/cyber-companion/    Current state and logs
$XDG_RUNTIME_DIR/cyber-companion/   Socket and transient events
$XDG_DATA_HOME/cyber-companion/     Installed avatar assets
```

No component should require root after installation.

## v0.8 implementation

The first implemented vertical slice uses `playerctl --all-players --follow` as an MPRIS
adapter. `cyber_companion.events.EventBus` delivers normalized events to the
state store, which persists a private JSON snapshot and selects a presentation
profile. The Wayland V-Pets adapter owns configuration translation; neither the
MPRIS adapter nor the state store knows renderer option names.

See [System integration v0.8](SYSTEM_INTEGRATION.md) for the runtime contract.

## Security boundary

The initial version will not read `/dev/input/event*`, join the `input` group,
capture screen contents or listen to the microphone. Future capabilities must be
optional adapters with explicit configuration.

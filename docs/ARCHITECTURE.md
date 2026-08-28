# Architecture

Cyber Companion separates system observation, behavior and rendering.

```text
system adapters -> event bus -> domain state -> behavior director
                                            -> presentation command
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

## Behavior configuration

Behavior policy lives in `config/behaviors.json`; adapters and renderers do not
contain priority policy. Each rule reads a versioned domain-state path, declares
its priority and produces a renderer-neutral presentation command. New adapters
can add domains without changing the director.

The highest-priority matching rule wins. Ties are resolved by stable behavior
name ordering, which makes selection deterministic and testable.

Enabled inputs live in `config/adapters.json`. Every adapter implements the same
`run`/`stop` lifecycle, publishes only normalized events and runs independently.
The event bus serializes concurrent publication so the state model observes a
total event order. Adapter-specific settings remain inside that adapter's entry.

## Presentation command

The state engine resolves competing events into one presentation command:

```json
{
  "version": 1,
  "profile": "media",
  "behavior": "music_sway",
  "intensity": 0.65,
  "transition": "smooth"
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

## v0.10 extensible behavior core

`BehaviorDirector` is the single presentation authority. `StateStore` reduces
events into independent domain snapshots and persists the last renderer-neutral
command. `BehaviorEngine` resolves the command from declarative, validated rules.
The Wayland V-Pets adapter only translates a selected profile into its native
signal; it does not inspect MPRIS or choose behavior.

Renderer-owned autonomous movement is disabled. In Wayland V-Pets,
`movement_radius=0` and `movement_speed=0` are the documented off values. This
prevents the upstream movement state machine from competing with the director.

The first live adapter remains MPRIS. PipeWire audio energy, system load,
libvirt and network status can be added as separate adapters over the same event
and domain-state contracts.

## v0.9 implementation history

The first implemented vertical slice uses `playerctl --all-players --follow` as an MPRIS
adapter. `cyber_companion.events.EventBus` delivers normalized events to the
state store, which persists a private JSON snapshot and selects a presentation
profile. The Wayland V-Pets adapter translates that profile into a native
media-state signal; neither the MPRIS adapter nor the state store knows renderer
signals or animation rows.

See [System integration v0.10](SYSTEM_INTEGRATION.md) for the current runtime contract.

## Security boundary

The initial version will not read `/dev/input/event*`, join the `input` group,
capture screen contents or listen to the microphone. Future capabilities must be
optional adapters with explicit configuration.

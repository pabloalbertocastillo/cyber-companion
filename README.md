# Cyber Companion

Cyber Companion is a metamorphic, holographic entity that reacts to the state
of a Gentoo Linux + Hyprland desktop.

The project starts as a lightweight desktop companion and is intentionally
designed to evolve into a visible interface for a local or remote AI system.

The v0.10 behavior core separates system adapters, normalized events, domain
state, declarative behavior policy and renderer commands. Wayland V-Pets is the
first renderer backend, not the owner of Wisp's behavior.

![Cyber Companion concept](assets/concept/companion-concept-v1.webp)

## Manifestations

- **Core** — minimal presence for normal system activity.
- **Wisp** — everyday desktop companion.
- **Sentinel** — direct interaction and important events.
- **Guardian** — rare, full-system manifestation.
- **Swarm** — transition between manifestations.

These are forms of the same distributed consciousness, not separate characters.

## Current status

The project is in **Phase 0: foundation and compatibility validation**.

- [x] Original visual concept
- [x] Event-driven architecture
- [x] Gentoo/Hyprland installation plan
- [x] Safe Wayland V-Pets configuration without keyboard capture
- [x] Validate Wayland V-Pets on the target system
- [x] Define the Wisp v1 production sprite contract
- [x] Produce a deterministic six-frame Wisp idle preview
- [x] Produce deterministic takeoff, flight and landing previews
- [x] Produce Wisp Rig v1 with independently animated arms
- [x] Correct Wayland ARGB premultiplied-alpha composition
- [ ] Replace the compiled atlas adapter with live rig composition
- [x] Add the MPRIS event bus for all compatible media players
- [x] Add native play/pause renderer state without configuration reloads
- [x] Add a declarative, priority-based behavior director
- [x] Disable renderer-owned autonomous travel
- [ ] Add libvirt, network, idle and thermal adapters
- [ ] Add an AI adapter

## Design principles

- Wayland- and Hyprland-aware.
- No global keyboard capture by default.
- Events are independent from avatar rendering.
- Renderers and avatars are replaceable.
- Minimal dependencies and no systemd requirement.
- Configuration and generated state remain in XDG user directories.
- System changes must be reversible.

## Repository layout

```text
assets/          Character concepts, source manifests and generated atlases
config/          Example renderer configuration
docs/            Architecture and Gentoo installation notes
scripts/         Diagnostics, validation and future runtime helpers
```

Start with [the Gentoo installation guide](docs/GENTOO_INSTALL.md). Do not add
your user to the `input` group for this project.

Avatar production follows [the Wisp sprite specification](docs/SPRITE_SPEC.md).
The default configuration now runs the v0.9 Rig v1 system preview. Its
three-layer source rig separates the body and both arms, stores pivots and
keyframes in JSON, and compiles seven 24-frame clips with smooth interpolation.
The media sequence activates, dances upright with broad arm motion, and returns
to the exact idle pose. The renderer build applies versioned alpha and native
media-state patches, while the sprite retains the doubled 224 px display
height. A third patch corrects upstream's zero-threshold `happy_kpm` validation.
The v0.3 atlas remains only as a rejected visual prototype.

Rebuild and validate the preview with:

```bash
./scripts/build-rig-v1.py
./scripts/build-rig-v1.py --system
python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-system-v0.9.png \
  assets/source/wisp/manifest-system-v0.9.json

./scripts/test-renderer-alpha.sh
./scripts/test-renderer-media.sh
```

## Upstream renderer candidate

Phase 0 evaluates [Wayland V-Pets](https://github.com/furudbat/wayland-vpets),
an MIT-licensed Wayland overlay that explicitly documents Hyprland,
multi-monitor support and runtime custom PNG sprite sheets. Cyber Companion does
not vendor or redistribute the upstream project. The reproducible build applies
three narrow local patches recorded in `UPSTREAM.lock`; it never silently switches
upstream revisions.

The renderer remains an adapter, not the core architecture. If it cannot expose
the state control needed for music and future integrations, it can be replaced
without redesigning the character or event model.

## Live system connection

The controller listens to every MPRIS-compatible media source through
`playerctl --all-players --follow`, emits normalized events and switches
Wayland V-Pets between calm and media activity through native renderer signals.
Spotify, browser media, VLC and mpv share the same adapter. It writes only a
private state snapshot and requires neither root nor keyboard access.

```bash
CYBER_COMPANION_MONITOR=<monitor-name> ./scripts/run-system.sh
```

Pause and resume any MPRIS player while the launcher runs. Detailed behavior
and runtime paths are documented in
[System integration v0.10](docs/SYSTEM_INTEGRATION.md).

## Licensing

No project license has been selected yet. Unless a license is added, the code,
documentation and original artwork remain under the repository owner's
copyright.

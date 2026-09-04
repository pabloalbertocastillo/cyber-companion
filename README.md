# Cyber Companion

Cyber Companion is a metamorphic, holographic entity that reacts to the state
of a Gentoo Linux + Hyprland desktop.

The v0.11 behavior core separates adapters, normalized events, domain state,
declarative behavior policy and renderer commands. Wayland V-Pets is the first
renderer backend, not the owner of Wisp's behavior.

![Cyber Companion concept](assets/concept/companion-concept-v1.webp)

## Wisp Visual v0.12

Visual v0.12 is a graphics-only upgrade built on the stable v0.11 behavior
contract. It replaces the default three-raster acceptance rig with a
deterministic character compositor rendered at four times the target
resolution and downsampled into the same seven-row Wayland V-Pets atlas.

![Wisp Visual v0.12](assets/previews/companion-wisp-system-v0.12.gif)

The avatar now has faceted armor, controlled holographic bloom, a breathing
core, visor micro-expression, shoulder and elbow articulation, an energy tail,
media-specific violet accents, and a separate upright system-processing visual
language. See [Wisp Visual v0.12](docs/VISUAL_V2.md).

## Manifestations

- **Core** — minimal presence for normal system activity.
- **Wisp** — everyday desktop companion.
- **Sentinel** — direct interaction and important events.
- **Guardian** — rare, full-system manifestation.
- **Swarm** — transition between manifestations.

These are forms of the same distributed consciousness, not separate
characters.

## Current status

The project is in **Phase 0: foundation and compatibility validation**.

- [x] Original visual concept
- [x] Event-driven architecture
- [x] Gentoo/Hyprland installation plan
- [x] Safe Wayland V-Pets configuration without keyboard capture
- [x] Wisp Rig v1 and renderer alpha correction
- [x] Native MPRIS and Linux system-presence states
- [x] Declarative priority-based behavior director
- [x] Wisp Visual v0.12 deterministic high-resolution renderer
- [ ] Accept Visual v0.12 on the target Gentoo desktop and both wallpapers
- [ ] Replace the compiled atlas adapter with live rig composition
- [ ] Add libvirt, network, idle and thermal adapters
- [ ] Add an AI adapter

## Design principles

- Wayland- and Hyprland-aware.
- No global keyboard capture by default.
- Events are independent from avatar rendering.
- Renderers and avatars are replaceable.
- Minimal runtime dependencies and no systemd requirement.
- Configuration and generated state remain in XDG user directories.
- System changes must be reversible.
- Visual output must be deterministic and mechanically testable.

## Repository layout

```text
assets/            Character concepts, manifests and review artifacts
config/            Example renderer and behavior configuration
cyber_companion/   Event, state, behavior and renderer-command core
docs/              Architecture, visual and Gentoo installation notes
renderer/          Patches for the pinned Wayland renderer
scripts/           Build, validation, diagnostics and runtime helpers
tests/             Python and isolated renderer contract tests
```

Start with [the Gentoo installation guide](docs/GENTOO_INSTALL.md). Do not add
your user to the `input` group for this project.

## Build the active avatar

Pillow is required only to generate the visual assets. The runtime consumes the
resulting PNG exactly as before.

```bash
python3 scripts/build-wisp-v2.py

python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-system-v0.12.png \
  assets/source/wisp/manifest-system-v0.12.json

python3 -m unittest discover -s tests
./scripts/test-renderer-alpha.sh
./scripts/test-renderer-media.sh
```

The compiler creates a 6144×1344 RGBA atlas containing seven 24-frame states,
an animated review GIF, a transparent still and a multi-background contact
sheet. The runtime atlas is ignored because the procedural model and manifest
are the reproducible source of truth. Rig v1 remains available as a fallback
and renderer regression fixture.

## Upstream renderer candidate

Phase 0 evaluates [Wayland V-Pets](https://github.com/furudbat/wayland-vpets),
an MIT-licensed Wayland overlay that documents Hyprland, multi-monitor support
and runtime custom PNG sprite sheets. Cyber Companion does not vendor or
redistribute the upstream project. The reproducible build applies four narrow
local patches recorded in `UPSTREAM.lock`.

Build the pinned renderer with the active visual atlas:

```bash
./scripts/build-renderer.sh
```

## Live system connection

The controller listens to every MPRIS-compatible media source, emits normalized
events and switches Wayland V-Pets between calm, media and system-presence
states through native renderer signals.

```bash
CYBER_COMPANION_MONITOR=<monitor-name> ./scripts/run-system.sh
```

## Versioning note

`v0.11` identifies the current behavior core. `Visual v0.12` identifies the
active graphics asset and build pipeline. The visual upgrade deliberately does
not alter event semantics.

## Licensing

No project license has been selected yet. Unless a license is added, the code,
documentation and original artwork remain under the repository owner's
copyright.

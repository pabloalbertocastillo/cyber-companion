# Wisp Visual v0.12

Status: **candidate production visual for the v0.11 behavior core**

Wisp Visual v0.12 is a graphics-only release. It does not change adapters,
normalized events, behavior priorities, native renderer signals or state
names. It replaces the default three-layer acceptance rig with a deterministic,
supersampled compositor that produces the same Wayland V-Pets atlas contract.

## Why the pipeline changed

Rig v1 proved state transitions, registration and renderer integration, but its
source consists of one body raster and two arm rasters. The compiler can rotate
the arms and apply a global scale or tilt; it cannot create convincing volume,
internal lighting, articulated elbows, facial micro-animation or
state-specific holographic effects.

Visual v0.12 changes the source of truth from three pre-painted layers to a
procedural character model. Every frame is reconstructed from the same
geometry, palette and animation functions. This preserves identity and
registration while allowing a materially richer renderer-ready atlas.

## Visual language

- Dark faceted armor separates the silhouette from bright and dark wallpapers.
- Cyan and teal establish the normal holographic body.
- Lime identifies the core and high-confidence system activity.
- Violet appears only during media activity.
- The visor supports breathing, focus and blink micro-animation.
- Two-segment arms provide shoulder and elbow articulation.
- The lower body dissolves into an energy tail anchored to the desktop.
- Glow rings, particles, data shards and scans communicate state without text.

## State semantics

| Renderer row | Domain meaning | Visual behavior |
|---|---|---|
| `idle` | calm fallback | slow hover, energy breathing, blink and tail flow |
| `start_working` | media enters | smooth transition into the media pose |
| `working` | media playing | asymmetric dance, violet accents and beat rings |
| `end_working` | media exits | exact return to the canonical idle pose |
| `start_moving` | sustained system load begins | transition into an upright analysis pose |
| `moving` | system busy | visor scan, data orbit and compact processing posture |
| `end_moving` | system load clears | exact return to the canonical idle pose |

The names `start_moving`, `moving` and `end_moving` remain compatibility slots
in the pinned Wayland V-Pets state machine. Wisp does not rotate 90 degrees or
travel autonomously.

## Rendering contract

The active manifest is
`assets/source/wisp/manifest-system-v0.12.json`.

| Property | Value |
|---|---:|
| Logical frame | 256 × 192 px |
| Internal render | 1024 × 768 px, 4× supersampling |
| Grid | 24 columns × 7 rows |
| Atlas | 6144 × 1344 px |
| Format | non-interlaced 8-bit RGBA PNG |
| Safe zone | x=[20,236), y=[12,180) |
| Stable anchor | x=128, y=168 |
| Playback | 42 ms per frame, approximately 24 FPS |

The final downsample uses Lanczos filtering. A safe-zone alpha feather prevents
filtered glow pixels from leaking into an adjacent atlas cell when the renderer
mirrors a frame.

## Source layout

```text
scripts/build-wisp-v2.py       Build orchestration and review artifacts
scripts/wisp_v2/model.py       Geometry, palette, poses and interpolation
scripts/wisp_v2/primitives.py  Supersampled compositing and alpha safety
scripts/wisp_v2/character.py   Character, articulation, lighting and effects
```

The files are renderer-independent. A future live renderer can reuse the pose
model without treating the compiled atlas as the authoritative source.

## Build and validation

Pillow is a build-time dependency. The runtime still needs only the generated
PNG and the existing renderer/controller stack.

```bash
python3 scripts/build-wisp-v2.py

python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-system-v0.12.png \
  assets/source/wisp/manifest-system-v0.12.json

python3 -m unittest discover -s tests
./scripts/test-renderer-alpha.sh
./scripts/test-renderer-media.sh
```

`build-wisp-v2.py` writes the ignored runtime atlas plus an animated review GIF,
a transparent still and a contact sheet over checkerboard, dark and light
backgrounds. Use `--atlas-only` for normal renderer builds and `--jobs 1` when
debugging a single deterministic execution path.

## Acceptance checklist

1. Idle remains calm at actual playback speed and does not look frozen.
2. Media activity is expressive without covering the monitor corner.
3. System-busy activity stays upright and is visually distinct from music.
4. Every transition is free of pops at the first and last frame.
5. Outline and glow work on black, white and the actual animated wallpaper.
6. No frame is clipped at the top, bottom or right-aligned monitor edge.
7. Runtime CPU remains negligible because expensive rendering occurs at build time.

## Non-goals

Visual v0.12 does not add audio-energy sampling, direct manipulation, a new
Wayland renderer, live skeletal composition, additional manifestations or AI
behavior. Those remain independent follow-on changes.

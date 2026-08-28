# Wisp Rig v1

Rig v1 is the first renderer-independent animation source for Wisp. It keeps
the approved v0.4 identity while separating the character into three layers:

| Part | Parent | Pivot | Purpose |
|---|---|---:|---|
| `body` | `root` | `95,150` | Head, torso, shoulders, core and tail |
| `left_arm` | `root` | `44,137` | Independent left shoulder rotation |
| `right_arm` | `root` | `146,137` | Independent right shoulder rotation |

The source canvas is 190×300. Layers retain the complete canvas so their pivot
coordinates remain identical and no registration metadata is lost.

## Animation contract

`assets/source/wisp/rig-v1/rig.json` defines the original movement clips.
`rig-system-v0.9.json` adds three explicit system-media clips before them:

| Clip | Frames | Nominal duration | Playback |
|---|---:|---:|---|
| `idle` | 24 | 1008 ms | loop |
| `start_working` | 24 | 1008 ms | once |
| `working` | 24 | 1008 ms | loop |
| `end_working` | 24 | 1008 ms | once |
| `start_moving` | 24 | 1000 ms | once |
| `moving` | 24 | 960 ms | loop |
| `end_moving` | 24 | 1000 ms | once |

Tracks are normalized from `0.0` to `1.0`. The compiler applies smoothstep
easing inside every pair of keyframes. Loop clips omit the duplicate endpoint;
one-shot clips include both endpoints so adjacent state boundaries match.

## Current adapter

Wayland V-Pets still receives a generated sprite sheet. This is an adapter
limitation, not the source format. The system atlas is 24 columns × 7 rows with
256×192 cells. Runtime playback uses 42 ms per frame, approximately 24 FPS.

The build applies three narrow patches to the pinned upstream commit. They
correct premultiplied alpha, provide native play/stop signals, and fix the
zero-threshold `happy_kpm` validation without enabling a nonexistent animation.

## Rebuild and verify

```bash
./scripts/build-rig-v1.py
./scripts/build-rig-v1.py --system

python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-movement-v0.7.png \
  assets/source/wisp/manifest-movement-v0.7.json

python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-system-v0.9.png \
  assets/source/wisp/manifest-system-v0.9.json

./scripts/build-renderer.sh
./scripts/test-renderer-alpha.sh
./scripts/test-renderer-media.sh
```

The next renderer adapter may evaluate these transforms live. It must preserve
the hierarchy and state names so system-event integrations remain independent
from rendering technology.

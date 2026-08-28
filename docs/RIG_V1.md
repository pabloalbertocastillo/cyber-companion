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

`assets/source/wisp/rig-v1/rig.json` defines four clips:

| Clip | Frames | Nominal duration | Playback |
|---|---:|---:|---|
| `idle` | 24 | 1008 ms | loop |
| `start_moving` | 24 | 1000 ms | once |
| `moving` | 24 | 960 ms | loop |
| `end_moving` | 24 | 1000 ms | once |

Tracks are normalized from `0.0` to `1.0`. The compiler applies smoothstep
easing inside every pair of keyframes. Loop clips omit the duplicate endpoint;
one-shot clips include both endpoints so adjacent state boundaries match.

## Current adapter

Wayland V-Pets still receives a generated sprite sheet. This is an adapter
limitation, not the source format. The atlas is 24 columns × 4 rows with
256×192 cells. Runtime playback uses 42 ms per frame, approximately 24 FPS.

The build applies `renderer/patches/0001-premultiplied-alpha.patch` to the
pinned upstream commit. Wayland `WL_SHM_FORMAT_ARGB8888` requires premultiplied
alpha; preserving destination alpha prevents translucent edges from becoming
opaque dark pixels over light wallpapers.

## Rebuild and verify

```bash
./scripts/build-rig-v1.py

python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-movement-v0.7.png \
  assets/source/wisp/manifest-movement-v0.7.json

./scripts/build-renderer.sh
./scripts/test-renderer-alpha.sh
```

The next renderer adapter may evaluate these transforms live. It must preserve
the hierarchy and state names so system-event integrations remain independent
from rendering technology.

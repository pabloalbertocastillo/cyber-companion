# Wisp Rig v1

Rig v1 is the first renderer-independent articulated source created for Wisp.
It remains a reproducible compatibility and regression fixture, but Wisp Visual
v0.12 is now the default visual pipeline. See `docs/VISUAL_V2.md`.

Rig v1 keeps the approved v0.4 identity while separating the character into
three full-canvas layers:

| Part | Parent | Pivot | Purpose |
|---|---|---:|---|
| `body` | `root` | `95,150` | Head, torso, shoulders, core and tail |
| `left_arm` | `root` | `44,137` | Independent left shoulder rotation |
| `right_arm` | `root` | `146,137` | Independent right shoulder rotation |

## Animation contract

`assets/source/wisp/rig-v1/rig-system-v0.11.json` retains the media clips and
repurposes the former movement rows as upright system-presence clips. Every
clip contains 24 frames and uses the same seven-row state order as Visual v0.12.

Tracks are normalized from `0.0` to `1.0`. Loop clips omit the duplicate
endpoint; one-shot clips include both endpoints so adjacent state boundaries
match.

## Historical adapter role

Wayland V-Pets receives a generated sprite sheet. The v0.11 rig atlas is 24
columns × 7 rows with 256×192 cells and uses 42 ms per frame. It is useful for
checking renderer behavior independently from the richer Visual v0.12
compositor.

The build applies four narrow patches to the pinned upstream commit. They
correct premultiplied alpha, provide native media and system-presence signals,
and fix zero-threshold `happy_kpm` validation without enabling a nonexistent
animation.

## Rebuild the fallback rig

```bash
./scripts/build-rig-v1.py
./scripts/build-rig-v1.py --system
./scripts/build-rig-v1.py --system-presence

python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-system-v0.11.png \
  assets/source/wisp/manifest-system-v0.11.json
```

Build the active default separately:

```bash
python3 scripts/build-wisp-v2.py
```

A future live renderer may consume either animation model directly. It must
preserve the state names so system-event integrations remain independent from
rendering technology.

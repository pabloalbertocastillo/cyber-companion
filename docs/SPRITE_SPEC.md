# Wisp Sprite Production Specification

Status: **normative for Wisp v1 assets**

This document defines the image contract for the first production Wisp avatar.
It replaces the experimental 2-column v0.3 atlas. The v0.3 file remains only as
a visual prototype and must not be treated as a production animation.

## Renderer baseline

The initial adapter targets Wayland V-Pets 5.0.2 at the commit pinned in
`UPSTREAM.lock`. Its custom loader divides a PNG into a uniform grid:

```text
cell width  = PNG width  / maximum configured frame count
cell height = PNG height / configured row count
```

Both divisions must be exact. Every cell has the same dimensions, including
unused cells. Packed or trimmed texture atlases are not compatible.

Primary references:

- [Wayland V-Pets custom sprite documentation](https://github.com/furudbat/wayland-vpets/blob/6475987f0dbebaef56b1db3e8997ea4c9cfd100e/examples/custom-sprite-sheets/README.md)
- [Grid calculation in the pinned image loader](https://github.com/furudbat/wayland-vpets/blob/6475987f0dbebaef56b1db3e8997ea4c9cfd100e/src/image_loader/load_images.cpp)
- [Custom state loading in the pinned renderer](https://github.com/furudbat/wayland-vpets/blob/6475987f0dbebaef56b1db3e8997ea4c9cfd100e/src/image_loader/custom/load_custom.cpp)
- [Animation state machine in the pinned renderer](https://github.com/furudbat/wayland-vpets/blob/6475987f0dbebaef56b1db3e8997ea4c9cfd100e/src/graphics/animation.cpp)

## Canonical atlas

The machine-readable source of truth is
`assets/source/wisp/manifest.json`.

| Property | Value |
|---|---:|
| Cell | 256 x 192 px |
| Grid | 8 columns x 7 rows |
| Atlas | 2048 x 1344 px |
| Format | PNG |
| Color | RGBA, 8 bits per channel |
| Background | Transparent alpha, never a baked checkerboard or chroma matte |
| Safe zone | x=[20,236), y=[12,180) |
| Pivot | x=128, y=168 |

Coordinates are local to every cell. `right` and `bottom` are exclusive.

The fixed pivot is a world-space origin at the base of the energy tail. It is
not the center of each frame's visible bounding box. Do not trim, recenter or
autocrop individual frames.

## State rows

Rows are zero-based in the manifest and appear top-to-bottom in the PNG.

| Row | State | Frames | Playback | Visual contract |
|---:|---|---:|---|---|
| 0 | `idle` | 6 | loop | Subtle hover and energy breathing |
| 1 | `start_working` | 4 | once | Idle to energized processing pose |
| 2 | `working` | 6 | loop | Stable processing activity |
| 3 | `end_working` | 4 | once | Processing pose back to idle |
| 4 | `start_moving` | 4 | once | Upright idle into forward flight |
| 5 | `moving` | 8 | loop | Continuous horizontal flight |
| 6 | `end_moving` | 4 | once | Braking and recovery to upright idle |

This order is a valid subset of the renderer's canonical state order. Do not
insert an unconfigured row. Each row is one coherent animation, not a set of
independent poses.

## Continuity rules

1. One canonical model, camera, projection, palette and light rig must be used
   for every frame.
2. Character identity and proportions must not be regenerated independently
   per frame.
3. The first `start_*` frame must match the source state closely.
4. The last `start_*` frame must lead into frame 1 of its loop.
5. The first `end_*` frame must continue from its loop.
6. The last `end_*` frame must lead back into `idle` frame 1.
7. Loop transitions, including last-frame to first-frame, must be reviewed at
   actual playback speed.
8. Armor, core, face and tail may deform, but the fixed pivot never moves.
9. Particles and glow must remain inside the safe zone in every frame.
10. Empty cells to the right of a shorter animation must have alpha zero.

Wayland V-Pets documents a rounding artifact when horizontally mirroring a
moving frame. The horizontal safe margins are mandatory to prevent pixels from
an adjacent cell leaking into the render.

## Rendering and color

- Render directly to a transparent film or canvas.
- Export a lossless PNG sequence before assembling the atlas.
- Use straight RGBA with a real alpha channel.
- Do not use green-screen extraction.
- Do not bake a checkerboard into RGB pixels.
- Do not resize individual frames after rendering.
- Review the exported sequence over black, white and the actual desktop
  wallpaper to detect halos and unintended color spill.

For a Blender pipeline, enable transparent film and render an RGBA PNG image
sequence. Blender recommends image sequences rather than rendering animation
directly to a video container:

- [Blender transparent film](https://docs.blender.org/manual/en/latest/render/cycles/render_settings/film.html)
- [Blender animation output](https://docs.blender.org/manual/en/latest/render/output/animation.html)

## Timing baseline

The initial runtime target is:

```ini
fps=60
animation_speed=125
```

`fps` controls the renderer cadence. A positive `animation_speed` controls the
duration of each animation frame and therefore overrides FPS for state-frame
advancement. At 125 ms the authored animation plays at 8 frames per second.

Timing is validated only after the image sequence passes continuity review.
Movement distance and velocity are tuned separately.

## Production workflow

1. Approve one canonical neutral model and camera.
2. Produce `idle` and approve its six-frame loop.
3. Produce and approve `start_moving`, `moving` and `end_moving` together.
4. Produce and approve the working transition set.
5. Export individual 256 x 192 RGBA PNG frames without trimming.
6. Assemble the 2048 x 1344 atlas from the manifest.
7. Run `scripts/validate-sprite.py`.
8. Preview every row independently and then exercise real renderer transitions.
9. Record a 20-30 second Wayland capture for final acceptance.

## Mechanical validation

Run:

```bash
python3 scripts/validate-sprite.py \
  assets/sprites/companion-wisp-v1.png \
  assets/source/wisp/manifest.json
```

The validator checks PNG integrity, exact format and dimensions, the alpha
channel, populated active cells, transparent unused cells and safe-zone
violations. Pivot and visual continuity still require human review because they
cannot be inferred reliably from an alpha bounding box.

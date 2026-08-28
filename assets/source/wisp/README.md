# Wisp source assets

This directory contains the renderer-independent source contract for Wisp v1.
Do not author directly into the final atlas.

Keep the editable master and individual RGBA frame sequences outside the
generated `assets/sprites/` output until their licensing and production format
have been selected. Every exported frame must use the canvas, safe zone and
pivot declared in `manifest.json`.

Expected source sequence names:

```text
idle/
start_working/
working/
end_working/
start_moving/
moving/
end_moving/
```

The atlas builder will place each sequence on the manifest row and leave unused
cells fully transparent. Renderer-specific packing must remain a generated step
so future renderers can reuse the same source animation.

## v0.4 idle acceptance preview

`companion-wisp-master-v0.4.png` is the single canonical raster used for every
frame in `companion-wisp-idle-v0.4.png`. The build script changes only its
height around the fixed tail pivot; it never regenerates individual poses.
This makes v0.4 suitable for judging scale, palette, edge quality and timing,
while movement and system-event states remain intentionally disabled.

## v0.5 movement acceptance preview

`companion-wisp-movement-v0.5.png` adds `start_moving`, `moving` and
`end_moving` without regenerating the character. The approved raster rotates
around one fixed visual center, and adjacent moving-loop frames differ by no
more than four degrees and four source pixels in height. This version tests
renderer transitions and autonomous travel before a layered production rig is
introduced.

## v0.6 articulated movement acceptance preview

`companion-wisp-movement-v0.6.png` keeps the approved v0.4 raster identity but
extracts its two disconnected arm components into a minimal deterministic rig.
Takeoff and landing now use six eased frames; the arms tuck independently while
the body tilts into flight. The runtime configuration doubles the displayed
height from 112 to 224 pixels and slows autonomous travel so the horizontal
state remains visible long enough to evaluate.

## v0.7 Rig v1 acceptance preview

`rig-v1/rig.json` replaces hard-coded pose arrays with a renderer-independent
hierarchy, pivots and animation tracks. Body, left arm and right arm are stored
as separate full-canvas RGBA layers. `scripts/build-rig-v1.py` interpolates the
keyframes with smoothstep easing and compiles four clips of 24 frames each.

The arms now travel through a visible 39–67 degree range during flight. A dark
two-pixel contour supports light wallpapers without changing the canonical
colors. The source rig remains editable independently from the generated atlas;
future live renderers can consume the same hierarchy instead of the compiled
Wayland V-Pets adapter.

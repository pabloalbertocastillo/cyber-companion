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

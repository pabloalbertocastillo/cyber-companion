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

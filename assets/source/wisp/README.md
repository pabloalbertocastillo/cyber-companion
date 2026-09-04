# Wisp source assets

This directory contains renderer-independent source contracts for Wisp. Do not
author directly into the final atlas.

Every exported frame must use the canvas, safe zone and pivot declared in its
manifest. Renderer-specific packing remains a generated step so future
renderers can reuse the character and animation model.

Expected state sequence names:

```text
idle/
start_working/
working/
end_working/
start_moving/
moving/
end_moving/
```

## Historical acceptance assets

- v0.4 established the canonical raster, scale and palette.
- v0.5 and v0.6 tested movement, fixed registration and arm extraction.
- v0.7/v0.11 Rig v1 introduced hierarchy, pivots, keyframes, native media and
  upright system-presence states.

These remain reproducible fallbacks and renderer regression fixtures.

## v0.12 Visual v2 production candidate

Visual v0.12 replaces the three-layer default with a procedural model under
`scripts/wisp_v2/`. It reconstructs the same Wisp for every frame at four times
the target resolution and then downsamples to the renderer cell.

The model adds:

- faceted armor and controlled holographic bloom;
- shoulder and elbow articulation;
- visor and blink micro-animation;
- a stable energy-tail anchor;
- media-specific violet beat effects;
- system-busy scans, data shards and focused posture;
- exact pixel continuity at all state boundaries.

The authoritative contract is `manifest-system-v0.12.json`. The generated
6144×1344 runtime atlas is intentionally ignored; the source code, manifest and
review artifacts are versioned.

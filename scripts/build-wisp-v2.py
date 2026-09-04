#!/usr/bin/env python3
"""Build the Wisp Visual v2 atlas and review artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as error:  # pragma: no cover - exercised on target hosts
    raise SystemExit(
        "Pillow is required to build Wisp Visual v2. On Gentoo install "
        "dev-python/pillow, or add Pillow to the active Python environment."
    ) from error

from wisp_v2 import (
    CELL_HEIGHT,
    CELL_WIDTH,
    COLUMNS,
    ROWS,
    SAFE_ZONE,
    STATE_ORDER,
    render_frame,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "assets/source/wisp/manifest-system-v0.12.json"
ATLAS_PATH = REPO_ROOT / "assets/sprites/companion-wisp-system-v0.12.png"
PREVIEW_PATH = REPO_ROOT / "assets/previews/companion-wisp-system-v0.12.gif"
STILL_PATH = REPO_ROOT / "assets/previews/companion-wisp-v0.12-still.png"
CONTACT_PATH = REPO_ROOT / "assets/previews/companion-wisp-v0.12-contact-sheet.png"


def render_task(task: tuple[str, int]) -> Image.Image:
    return render_frame(*task)


def validate_manifest() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    image = manifest["image"]
    expected = {
        "columns": COLUMNS,
        "rows": ROWS,
        "cell_width": CELL_WIDTH,
        "cell_height": CELL_HEIGHT,
    }
    actual = {key: int(image[key]) for key in expected}
    if actual != expected:
        raise SystemExit(
            f"Visual v2 code/manifest geometry mismatch: {actual} != {expected}"
        )
    safe = manifest["safe_zone"]
    manifest_safe = (
        int(safe["left"]),
        int(safe["top"]),
        int(safe["right"]),
        int(safe["bottom"]),
    )
    if manifest_safe != SAFE_ZONE:
        raise SystemExit(
            f"Visual v2 code/manifest safe-zone mismatch: {manifest_safe} != {SAFE_ZONE}"
        )
    states = tuple(state["name"] for state in manifest["states"])
    if states != STATE_ORDER:
        raise SystemExit(f"Visual v2 state order mismatch: {states} != {STATE_ORDER}")
    if any(int(state["frames"]) != COLUMNS for state in manifest["states"]):
        raise SystemExit(f"Every Visual v2 state must contain {COLUMNS} frames")
    return manifest


def render_all(jobs: int) -> dict[str, list[Image.Image]]:
    tasks = [(state, frame) for state in STATE_ORDER for frame in range(COLUMNS)]
    if jobs == 1:
        rendered = [render_task(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            rendered = list(pool.map(render_task, tasks, chunksize=2))

    frames: dict[str, list[Image.Image]] = {state: [] for state in STATE_ORDER}
    for (state, _), image in zip(tasks, rendered):
        frames[state].append(image)
    return frames


def build_atlas(frames: dict[str, list[Image.Image]]) -> Image.Image:
    atlas = Image.new(
        "RGBA",
        (CELL_WIDTH * COLUMNS, CELL_HEIGHT * ROWS),
        (0, 0, 0, 0),
    )
    for row, state in enumerate(STATE_ORDER):
        for column, frame in enumerate(frames[state]):
            atlas.alpha_composite(frame, (column * CELL_WIDTH, row * CELL_HEIGHT))
    return atlas


def checkerboard(size: tuple[int, int], square: int = 12) -> Image.Image:
    background = Image.new("RGB", size, (25, 27, 32))
    draw = ImageDraw.Draw(background)
    for y in range(0, size[1], square):
        for x in range(0, size[0], square):
            if (x // square + y // square) % 2:
                draw.rectangle(
                    (x, y, x + square - 1, y + square - 1),
                    fill=(44, 47, 55),
                )
    return background


def build_contact_sheet(frames: dict[str, list[Image.Image]]) -> Image.Image:
    title_height = 26
    card_height = CELL_HEIGHT + title_height
    sheet = Image.new("RGB", (CELL_WIDTH * 3, card_height * 3), (7, 10, 17))
    picks = (
        ("idle", 0),
        ("idle", 17),
        ("start_working", 17),
        ("working", 3),
        ("working", 9),
        ("working", 15),
        ("moving", 2),
        ("moving", 10),
        ("moving", 18),
    )
    draw = ImageDraw.Draw(sheet)
    for index, (state, frame_index) in enumerate(picks):
        x = index % 3 * CELL_WIDTH
        y = index // 3 * card_height
        if index % 2 == 0:
            background = checkerboard((CELL_WIDTH, CELL_HEIGHT))
        else:
            background = Image.new(
                "RGB",
                (CELL_WIDTH, CELL_HEIGHT),
                (4, 7, 13) if index % 3 else (224, 229, 232),
            )
        frame = frames[state][frame_index]
        background.paste(frame, (0, 0), frame)
        sheet.paste(background, (x, y + title_height))
        draw.text(
            (x + 8, y + 7),
            f"{state} · {frame_index + 1:02d}",
            fill=(220, 240, 245),
        )
    return sheet


def build_preview(frames: dict[str, list[Image.Image]]) -> list[Image.Image]:
    sequence: list[Image.Image] = []
    plan = (
        ("idle", 1),
        ("start_working", 1),
        ("working", 2),
        ("end_working", 1),
        ("idle", 1),
        ("start_moving", 1),
        ("moving", 2),
        ("end_moving", 1),
        ("idle", 1),
    )
    for state, repeats in plan:
        for _ in range(repeats):
            sequence.extend(frames[state][::2])

    preview: list[Image.Image] = []
    for frame in sequence:
        background = Image.new("RGBA", frame.size, (5, 8, 15, 255))
        background.alpha_composite(frame)
        preview.append(
            background.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
        )
    return preview


def save_outputs(
    frames: dict[str, list[Image.Image]],
    atlas_only: bool,
) -> None:
    ATLAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    atlas = build_atlas(frames)
    atlas.save(ATLAS_PATH, optimize=True, compress_level=7)
    print(f"Built: {ATLAS_PATH}")

    if atlas_only:
        return

    frames["idle"][0].save(STILL_PATH, optimize=True)
    build_contact_sheet(frames).save(CONTACT_PATH, optimize=True)
    preview = build_preview(frames)
    preview[0].save(
        PREVIEW_PATH,
        save_all=True,
        append_images=preview[1:],
        duration=84,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Built: {STILL_PATH}")
    print(f"Built: {CONTACT_PATH}")
    print(f"Built: {PREVIEW_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jobs",
        type=int,
        default=min(8, os.cpu_count() or 1),
        help="parallel render workers; default: min(8, CPU count)",
    )
    parser.add_argument(
        "--atlas-only",
        action="store_true",
        help="skip GIF, still and contact-sheet review artifacts",
    )
    arguments = parser.parse_args()
    if arguments.jobs < 1:
        parser.error("--jobs must be at least 1")

    validate_manifest()
    frames = render_all(arguments.jobs)
    save_outputs(frames, arguments.atlas_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Compile Wisp Rig v1 keyframes into a Wayland V-Pets sprite sheet."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RIG_DIR = REPO_ROOT / "assets/source/wisp/rig-v1"
RIG_FILE = RIG_DIR / "rig.json"
BUILD_DIR = REPO_ROOT / "build/rig-v1"
ATLAS = REPO_ROOT / "assets/sprites/companion-wisp-movement-v0.7.png"
PREVIEW = REPO_ROOT / "assets/previews/companion-wisp-movement-v0.7.gif"


def image_tool() -> str:
    for candidate in ("magick", "convert"):
        path = shutil.which(candidate)
        if path:
            return path
    raise SystemExit("ImageMagick is required (magick or convert).")


def run(*args: str | Path) -> None:
    subprocess.run([str(value) for value in args], check=True)


def smoothstep(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def sample(track: list[list[float]], position: float) -> float:
    if position <= track[0][0]:
        return float(track[0][1])
    if position >= track[-1][0]:
        return float(track[-1][1])

    for left, right in zip(track, track[1:]):
        if left[0] <= position <= right[0]:
            span = float(right[0] - left[0])
            local = 0.0 if span == 0 else (position - float(left[0])) / span
            eased = smoothstep(local)
            return float(left[1]) + (float(right[1]) - float(left[1])) * eased
    raise AssertionError(f"Position {position} is outside track")


def frame_position(index: int, count: int, loop: bool) -> float:
    if count <= 1:
        return 0.0
    return index / count if loop else index / (count - 1)


def render_frame(tool: str, rig: dict, clip: dict, index: int, output: Path) -> None:
    position = frame_position(index, clip["frames"], clip["loop"])
    tracks = clip["tracks"]
    frame_dir = output.parent / f"{output.stem}-work"
    frame_dir.mkdir(parents=True, exist_ok=True)

    transformed: dict[str, Path] = {}
    for part in sorted(rig["parts"], key=lambda item: item["z"]):
        source = RIG_DIR / part["image"]
        if not source.is_file():
            raise SystemExit(f"Missing rig layer: {source}")

        angle = sample(tracks.get(f"{part['name']}.rotation", [[0, 0], [1, 0]]), position)
        if math.isclose(angle, 0.0, abs_tol=0.0001):
            transformed[part["name"]] = source
            continue

        destination = frame_dir / f"{part['name']}.png"
        pivot_x, pivot_y = part["pivot"]
        run(
            tool,
            source,
            "-virtual-pixel",
            "transparent",
            "-distort",
            "SRT",
            f"{pivot_x},{pivot_y} 1 {angle:.5f} {pivot_x},{pivot_y}",
            f"PNG32:{destination}",
        )
        transformed[part["name"]] = destination

    source_width, source_height = rig["source_canvas"]
    assembled = frame_dir / "assembled.png"
    command: list[str | Path] = [tool, "-size", f"{source_width}x{source_height}", "xc:none"]
    for part in sorted(rig["parts"], key=lambda item: item["z"]):
        command.extend([transformed[part["name"]], "-compose", "over", "-composite"])
    command.append(f"PNG32:{assembled}")
    run(*command)

    root_rotation = sample(tracks["root.rotation"], position)
    root_scale_y = sample(tracks["root.scale_y"], position)
    root_offset_y = round(sample(tracks["root.offset_y"], position))
    render_width, render_height = rig["render_size"]
    scaled_height = max(1, round(render_height * root_scale_y))
    cell_width, cell_height = rig["cell"]

    clean_frame = frame_dir / "clean.png"
    run(
        tool,
        assembled,
        "-resize",
        f"{render_width}x{scaled_height}!",
        "-background",
        "none",
        "-rotate",
        f"{root_rotation:.5f}",
        "(",
        "-size",
        f"{cell_width}x{cell_height}",
        "xc:none",
        ")",
        "+swap",
        "-gravity",
        "Center",
        "-geometry",
        f"+0+{root_offset_y}",
        "-composite",
        f"PNG32:{clean_frame}",
    )

    outline = rig.get("outline")
    if not outline or int(outline.get("radius", 0)) <= 0:
        run(tool, clean_frame, "-strip", f"PNG32:{output}")
        return

    mask = frame_dir / "outline-mask.png"
    outline_frame = frame_dir / "outline.png"
    radius = int(outline["radius"])
    run(
        tool,
        clean_frame,
        "-alpha",
        "extract",
        "-morphology",
        "Dilate",
        f"Disk:{radius}",
        mask,
    )
    run(
        tool,
        "-size",
        f"{cell_width}x{cell_height}",
        f"xc:{outline['color']}",
        mask,
        "-alpha",
        "off",
        "-compose",
        "CopyOpacity",
        "-composite",
        f"PNG32:{outline_frame}",
    )
    run(
        tool,
        "-size",
        f"{cell_width}x{cell_height}",
        "xc:none",
        outline_frame,
        "-compose",
        "over",
        "-composite",
        clean_frame,
        "-composite",
        "-strip",
        f"PNG32:{output}",
    )


def main() -> int:
    rig = json.loads(RIG_FILE.read_text(encoding="utf-8"))
    tool = image_tool()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    ATLAS.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)

    rows: list[Path] = []
    rendered: dict[str, list[Path]] = {}
    expected_columns = max(int(clip["frames"]) for clip in rig["clips"])

    for clip in rig["clips"]:
        clip_dir = BUILD_DIR / clip["name"]
        clip_dir.mkdir(parents=True, exist_ok=True)
        frames: list[Path] = []
        for index in range(int(clip["frames"])):
            frame = clip_dir / f"{index + 1:02d}.png"
            render_frame(tool, rig, clip, index, frame)
            frames.append(frame)
        rendered[clip["name"]] = frames

        if len(frames) != expected_columns:
            raise SystemExit("Rig v1 requires equal frame counts in this acceptance atlas.")
        row = BUILD_DIR / f"row-{clip['name']}.png"
        run(tool, *frames, "+append", f"PNG32:{row}")
        rows.append(row)

    run(tool, *rows, "-append", "-strip", f"PNG32:{ATLAS}")

    preview_command: list[str | Path] = [tool]
    preview_sequence = ["idle", "start_moving", "moving", "moving", "end_moving", "idle"]
    clips = {clip["name"]: clip for clip in rig["clips"]}
    for name in preview_sequence:
        delay = max(1, round((int(clips[name]["duration_ms"]) / int(clips[name]["frames"])) / 10))
        preview_command.extend(["-delay", str(delay), *rendered[name]])
    preview_command.extend(["-dispose", "background", "-loop", "0", PREVIEW])
    run(*preview_command)

    print(f"Built: {ATLAS}")
    print(f"Built: {PREVIEW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

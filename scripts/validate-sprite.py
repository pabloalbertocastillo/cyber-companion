#!/usr/bin/env python3
"""Validate a Cyber Companion PNG atlas against its production manifest."""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CANONICAL_STATE_ORDER = (
    "idle",
    "boring",
    "start_writing",
    "writing",
    "end_writing",
    "happy",
    "asleep",
    "sleep",
    "wake_up",
    "start_working",
    "working",
    "end_working",
    "start_moving",
    "moving",
    "end_moving",
    "start_running",
    "running",
    "end_running",
)


class ValidationError(Exception):
    """Raised when an atlas cannot satisfy the mechanical contract."""


@dataclass(frozen=True)
class PngImage:
    width: int
    height: int
    bit_depth: int
    color_type: int
    rows: tuple[bytes, ...]


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distance_left = abs(estimate - left)
    distance_above = abs(estimate - above)
    distance_upper_left = abs(estimate - upper_left)
    if distance_left <= distance_above and distance_left <= distance_upper_left:
        return left
    if distance_above <= distance_upper_left:
        return above
    return upper_left


def _unfilter(scanline: bytes, previous: bytes, filter_type: int, bpp: int) -> bytes:
    reconstructed = bytearray(len(scanline))
    for index, value in enumerate(scanline):
        left = reconstructed[index - bpp] if index >= bpp else 0
        above = previous[index] if previous else 0
        upper_left = previous[index - bpp] if previous and index >= bpp else 0
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = above
        elif filter_type == 3:
            predictor = (left + above) // 2
        elif filter_type == 4:
            predictor = _paeth(left, above, upper_left)
        else:
            raise ValidationError(f"unsupported PNG filter type: {filter_type}")
        reconstructed[index] = (value + predictor) & 0xFF
    return bytes(reconstructed)


def read_png(path: Path) -> PngImage:
    raw = path.read_bytes()
    if not raw.startswith(PNG_SIGNATURE):
        raise ValidationError("file is not a PNG")

    cursor = len(PNG_SIGNATURE)
    header: tuple[int, int, int, int, int, int, int] | None = None
    compressed = bytearray()
    found_end = False

    while cursor < len(raw):
        if cursor + 12 > len(raw):
            raise ValidationError("truncated PNG chunk")
        length = struct.unpack(">I", raw[cursor : cursor + 4])[0]
        chunk_type = raw[cursor + 4 : cursor + 8]
        data_start = cursor + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(raw):
            raise ValidationError("truncated PNG chunk data")
        chunk_data = raw[data_start:data_end]
        expected_crc = struct.unpack(">I", raw[data_end:crc_end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            name = chunk_type.decode("ascii", errors="replace")
            raise ValidationError(f"CRC mismatch in PNG chunk {name}")

        if chunk_type == b"IHDR":
            if header is not None or length != 13:
                raise ValidationError("invalid IHDR chunk")
            header = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            found_end = True
            break
        cursor = crc_end

    if header is None or not found_end:
        raise ValidationError("PNG is missing IHDR or IEND")

    width, height, bit_depth, color_type, compression, filtering, interlace = header
    if bit_depth != 8 or color_type != 6:
        raise ValidationError(
            f"PNG must be 8-bit RGBA (color type 6), got bit depth {bit_depth}, "
            f"color type {color_type}"
        )
    if compression != 0 or filtering != 0 or interlace != 0:
        raise ValidationError("PNG must use standard compression/filtering and be non-interlaced")

    try:
        decoded = zlib.decompress(bytes(compressed))
    except zlib.error as error:
        raise ValidationError(f"cannot decompress PNG image data: {error}") from error

    stride = width * 4
    expected_size = height * (stride + 1)
    if len(decoded) != expected_size:
        raise ValidationError(
            f"decoded PNG size mismatch: expected {expected_size}, got {len(decoded)}"
        )

    rows: list[bytes] = []
    offset = 0
    previous = b""
    for _ in range(height):
        filter_type = decoded[offset]
        scanline = decoded[offset + 1 : offset + 1 + stride]
        row = _unfilter(scanline, previous, filter_type, 4)
        rows.append(row)
        previous = row
        offset += stride + 1

    return PngImage(width, height, bit_depth, color_type, tuple(rows))


def _cell_bbox(
    image: PngImage, cell_width: int, cell_height: int, column: int, row: int
) -> tuple[int, int, int, int] | None:
    minimum_x = cell_width
    minimum_y = cell_height
    maximum_x = -1
    maximum_y = -1
    origin_x = column * cell_width
    origin_y = row * cell_height

    for local_y in range(cell_height):
        scanline = image.rows[origin_y + local_y]
        for local_x in range(cell_width):
            alpha = scanline[(origin_x + local_x) * 4 + 3]
            if alpha:
                minimum_x = min(minimum_x, local_x)
                minimum_y = min(minimum_y, local_y)
                maximum_x = max(maximum_x, local_x)
                maximum_y = max(maximum_y, local_y)

    if maximum_x < 0:
        return None
    return minimum_x, minimum_y, maximum_x, maximum_y


def validate(atlas_path: Path, manifest_path: Path) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    image_contract = manifest["image"]
    safe_zone = manifest["safe_zone"]
    pivot = manifest["pivot"]
    states = manifest["states"]

    cell_width = int(image_contract["cell_width"])
    cell_height = int(image_contract["cell_height"])
    columns = int(image_contract["columns"])
    rows = int(image_contract["rows"])
    expected_width = cell_width * columns
    expected_height = cell_height * rows

    image = read_png(atlas_path)
    errors: list[str] = []
    report: list[str] = [
        f"PNG: {image.width}x{image.height}, RGBA 8-bit",
        f"Grid: {columns}x{rows}, cells {cell_width}x{cell_height}",
    ]

    if image.width != expected_width or image.height != expected_height:
        errors.append(
            f"atlas dimensions must be {expected_width}x{expected_height}, "
            f"got {image.width}x{image.height}"
        )
        return report + [f"ERROR: {message}" for message in errors]

    if int(manifest.get("schema_version", 0)) != 1:
        errors.append("manifest schema_version must be 1")
    if str(image_contract.get("format", "")).lower() != "png":
        errors.append("manifest image format must be png")
    if str(image_contract.get("color_mode", "")).lower() != "rgba":
        errors.append("manifest image color_mode must be rgba")
    if int(image_contract.get("bit_depth", 0)) != 8:
        errors.append("manifest image bit_depth must be 8")

    states_by_row: dict[int, dict[str, object]] = {}
    state_order: list[int] = []
    state_names: set[str] = set()
    for state in states:
        row = int(state["row"])
        frames = int(state["frames"])
        name = str(state["name"])
        if name not in CANONICAL_STATE_ORDER:
            errors.append(f"state {name} is not supported by the renderer profile")
            continue
        if name in state_names:
            errors.append(f"state {name} is assigned more than once")
            continue
        state_names.add(name)
        state_order.append(CANONICAL_STATE_ORDER.index(name))
        if row < 0 or row >= rows:
            errors.append(f"state {name} has invalid row {row}")
            continue
        if row in states_by_row:
            errors.append(f"row {row} is assigned more than once")
            continue
        if frames < 1 or frames > columns:
            errors.append(f"state {name} has invalid frame count {frames}")
            continue
        states_by_row[row] = state

    if state_order != sorted(state_order):
        errors.append("states do not follow the canonical Wayland V-Pets row order")

    if set(states_by_row) != set(range(rows)):
        missing = sorted(set(range(rows)) - set(states_by_row))
        errors.append(f"manifest does not assign every atlas row; missing {missing}")

    left = int(safe_zone["left"])
    top = int(safe_zone["top"])
    right = int(safe_zone["right"])
    bottom = int(safe_zone["bottom"])
    if not (0 <= left < right <= cell_width and 0 <= top < bottom <= cell_height):
        errors.append("safe zone is outside the cell or has invalid bounds")
    pivot_x = int(pivot["x"])
    pivot_y = int(pivot["y"])
    if not (left <= pivot_x < right and top <= pivot_y < bottom):
        errors.append("pivot must be inside the safe zone")

    for row in range(rows):
        state = states_by_row.get(row)
        if state is None:
            continue
        name = str(state["name"])
        frames = int(state["frames"])
        for column in range(columns):
            bbox = _cell_bbox(image, cell_width, cell_height, column, row)
            label = f"{name}[{column + 1}]"
            if column < frames:
                if bbox is None:
                    errors.append(f"{label} is empty")
                    continue
                minimum_x, minimum_y, maximum_x, maximum_y = bbox
                report.append(
                    f"{label}: bbox x={minimum_x}..{maximum_x}, y={minimum_y}..{maximum_y}"
                )
                if (
                    minimum_x < left
                    or minimum_y < top
                    or maximum_x >= right
                    or maximum_y >= bottom
                ):
                    errors.append(f"{label} has visible pixels outside the safe zone")
            elif bbox is not None:
                errors.append(f"unused cell {label} is not fully transparent")

    return report + [f"ERROR: {message}" for message in errors]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("atlas", type=Path, help="PNG atlas to validate")
    parser.add_argument("manifest", type=Path, help="JSON production manifest")
    arguments = parser.parse_args()

    try:
        report = validate(arguments.atlas, arguments.manifest)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for line in report:
        print(line)
    errors = [line for line in report if line.startswith("ERROR:")]
    if errors:
        print(f"Result: FAIL ({len(errors)} error(s))", file=sys.stderr)
        return 1
    print("Result: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

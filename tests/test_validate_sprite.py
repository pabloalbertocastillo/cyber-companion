#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_sprite", ROOT / "scripts" / "validate-sprite.py"
)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


def write_rgba_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    scanlines = bytearray()
    stride = width * 4
    for row in range(height):
        scanlines.append(0)
        start = row * stride
        scanlines.extend(pixels[start : start + stride])
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(
        VALIDATOR.PNG_SIGNATURE
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(bytes(scanlines)))
        + png_chunk(b"IEND", b"")
    )


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.manifest_path = self.directory / "manifest.json"
        self.atlas_path = self.directory / "atlas.png"
        self.manifest = {
            "schema_version": 1,
            "image": {
                "format": "png",
                "color_mode": "rgba",
                "bit_depth": 8,
                "cell_width": 16,
                "cell_height": 12,
                "columns": 4,
                "rows": 2,
            },
            "safe_zone": {"left": 2, "top": 1, "right": 14, "bottom": 11},
            "pivot": {"x": 8, "y": 10},
            "states": [
                {"name": "idle", "row": 0, "frames": 2},
                {"name": "moving", "row": 1, "frames": 4},
            ],
        }
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.width = 64
        self.height = 24
        self.pixels = bytearray(self.width * self.height * 4)
        for row, frames in ((0, 2), (1, 4)):
            for column in range(frames):
                for y in range(3, 9):
                    for x in range(4, 12):
                        absolute_x = column * 16 + x
                        absolute_y = row * 12 + y
                        offset = (absolute_y * self.width + absolute_x) * 4
                        self.pixels[offset : offset + 4] = b"\x10\x80\xff\xff"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def validate(self) -> list[str]:
        write_rgba_png(self.atlas_path, self.width, self.height, self.pixels)
        return VALIDATOR.validate(self.atlas_path, self.manifest_path)

    def test_valid_atlas_passes(self) -> None:
        report = self.validate()
        self.assertFalse(any(line.startswith("ERROR:") for line in report))

    def test_visible_pixel_in_unused_cell_fails(self) -> None:
        absolute_x = 2 * 16 + 5
        absolute_y = 5
        offset = (absolute_y * self.width + absolute_x) * 4
        self.pixels[offset : offset + 4] = b"\xff\xff\xff\xff"
        report = self.validate()
        self.assertTrue(any("unused cell" in line for line in report))

    def test_safe_zone_violation_fails(self) -> None:
        absolute_x = 1
        absolute_y = 5
        offset = (absolute_y * self.width + absolute_x) * 4
        self.pixels[offset : offset + 4] = b"\xff\xff\xff\xff"
        report = self.validate()
        self.assertTrue(any("outside the safe zone" in line for line in report))

    def test_wrong_dimensions_fail(self) -> None:
        write_rgba_png(self.atlas_path, 16, 12, bytearray(16 * 12 * 4))
        report = VALIDATOR.validate(self.atlas_path, self.manifest_path)
        self.assertTrue(any("atlas dimensions" in line for line in report))

    def test_invalid_state_order_fails(self) -> None:
        self.manifest["states"].reverse()
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        report = self.validate()
        self.assertTrue(any("canonical Wayland V-Pets" in line for line in report))


if __name__ == "__main__":
    unittest.main()

import json
import math
import sys
import unittest
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from wisp_v2 import (  # noqa: E402
    CELL_HEIGHT,
    CELL_WIDTH,
    COLUMNS,
    ROWS,
    SAFE_ZONE,
    STATE_ORDER,
    Pose,
    pose_for,
    render_frame,
)


MANIFEST = json.loads(
    (ROOT / "assets/source/wisp/manifest-system-v0.12.json").read_text(
        encoding="utf-8"
    )
)


@lru_cache(maxsize=None)
def frame(state: str, index: int):
    return render_frame(state, index)


class WispVisualV2Tests(unittest.TestCase):
    def test_manifest_matches_renderer_contract(self):
        image = MANIFEST["image"]
        self.assertEqual(image["columns"], COLUMNS)
        self.assertEqual(image["rows"], ROWS)
        self.assertEqual(image["cell_width"], CELL_WIDTH)
        self.assertEqual(image["cell_height"], CELL_HEIGHT)
        safe = MANIFEST["safe_zone"]
        self.assertEqual(
            (safe["left"], safe["top"], safe["right"], safe["bottom"]),
            SAFE_ZONE,
        )
        self.assertEqual(
            tuple(state["name"] for state in MANIFEST["states"]),
            STATE_ORDER,
        )
        self.assertTrue(all(state["frames"] == COLUMNS for state in MANIFEST["states"]))

    def test_pose_values_are_finite(self):
        for state in STATE_ORDER:
            for index in (0, COLUMNS // 2, COLUMNS - 1):
                pose = pose_for(state, index)
                for field in Pose.__dataclass_fields__:
                    self.assertTrue(
                        math.isfinite(getattr(pose, field)),
                        f"{state}[{index}].{field}",
                    )

    def test_transition_endpoints_are_pixel_exact(self):
        boundaries = (
            ("idle", 0, "start_working", 0),
            ("start_working", 23, "working", 0),
            ("working", 0, "end_working", 0),
            ("end_working", 23, "idle", 0),
            ("idle", 0, "start_moving", 0),
            ("start_moving", 23, "moving", 0),
            ("moving", 0, "end_moving", 0),
            ("end_moving", 23, "idle", 0),
        )
        for left_state, left_index, right_state, right_index in boundaries:
            self.assertEqual(
                frame(left_state, left_index).tobytes(),
                frame(right_state, right_index).tobytes(),
                f"{left_state}[{left_index}] -> {right_state}[{right_index}]",
            )

    def test_representative_frames_are_rgba_and_inside_safe_zone(self):
        left, top, right, bottom = SAFE_ZONE
        for state in STATE_ORDER:
            image = frame(state, 11)
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.size, (CELL_WIDTH, CELL_HEIGHT))
            bbox = image.getchannel("A").getbbox()
            self.assertIsNotNone(bbox, state)
            x0, y0, x1, y1 = bbox
            self.assertGreaterEqual(x0, left, state)
            self.assertGreaterEqual(y0, top, state)
            self.assertLessEqual(x1, right, state)
            self.assertLessEqual(y1, bottom, state)

    def test_rendering_is_deterministic(self):
        first = render_frame("working", 7)
        second = render_frame("working", 7)
        self.assertEqual(first.tobytes(), second.tobytes())


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RIG = json.loads(
    (ROOT / "assets/source/wisp/rig-v1/rig.json").read_text(encoding="utf-8")
)


class RigV1Tests(unittest.TestCase):
    def setUp(self):
        self.clips = {clip["name"]: clip for clip in RIG["clips"]}

    def assert_pose_equal(self, first, first_end, second, second_end):
        tracks = set(first["tracks"]) | set(second["tracks"])
        for track_name in tracks:
            first_track = first["tracks"].get(track_name, [[0, 0], [1, 0]])
            second_track = second["tracks"].get(track_name, [[0, 0], [1, 0]])
            self.assertEqual(
                first_track[first_end][1],
                second_track[second_end][1],
                track_name,
            )

    def test_layers_exist_and_share_source_canvas(self):
        expected_signature = b"\x89PNG\r\n\x1a\n"
        expected_dimensions = tuple(RIG["source_canvas"])
        for part in RIG["parts"]:
            path = ROOT / "assets/source/wisp/rig-v1" / part["image"]
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(expected_signature), path)
            width = int.from_bytes(raw[16:20], "big")
            height = int.from_bytes(raw[20:24], "big")
            self.assertEqual((width, height), expected_dimensions, path)

    def test_tracks_are_normalized_and_ordered(self):
        for clip in RIG["clips"]:
            self.assertEqual(clip["frames"], 24)
            for name, track in clip["tracks"].items():
                positions = [keyframe[0] for keyframe in track]
                self.assertEqual(positions[0], 0.0, name)
                self.assertEqual(positions[-1], 1.0, name)
                self.assertEqual(positions, sorted(positions), name)

    def test_loop_seams_close(self):
        for name in ("idle", "moving"):
            clip = self.clips[name]
            for track_name, track in clip["tracks"].items():
                self.assertEqual(track[0][1], track[-1][1], track_name)

    def test_state_boundaries_match(self):
        self.assert_pose_equal(self.clips["idle"], -1, self.clips["start_moving"], 0)
        self.assert_pose_equal(self.clips["start_moving"], -1, self.clips["moving"], 0)
        self.assert_pose_equal(self.clips["moving"], 0, self.clips["end_moving"], 0)
        self.assert_pose_equal(self.clips["end_moving"], -1, self.clips["idle"], 0)


if __name__ == "__main__":
    unittest.main()

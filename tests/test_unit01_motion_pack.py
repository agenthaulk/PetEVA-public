import json
from pathlib import Path
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOTION_PACK = (
    ROOT
    / "assets/codex-pets/eva-01/source/frames"
    / "2026-05-13-unit01-motion-12frame/runtime-12frame-clean"
)
EXPECTED_ACTIONS = [
    "walking",
    "running",
    "crawling",
    "diagonal-jump",
    "diagonal-jump-right",
    "vertical-jump",
]
GROUND_ACTIONS = ("walking", "running", "crawling")


class Unit01MotionPackTest(unittest.TestCase):
    def test_manifest_records_the_expected_action_set(self):
        manifest = read_manifest()

        self.assertEqual(manifest["frameCount"], 12)
        self.assertEqual(manifest["cellWidth"], 192)
        self.assertEqual(manifest["cellHeight"], 208)
        self.assertEqual(list(manifest["actions"]), EXPECTED_ACTIONS)
        for action_name in EXPECTED_ACTIONS:
            self.assertEqual(manifest["actions"][action_name]["frames"], 12)

    def test_manifest_records_manual_asset_repairs(self):
        manifest = read_manifest()

        self.assertEqual(
            manifest["actions"]["walking"]["sourceType"],
            "backup-6frame-expanded",
        )
        self.assertEqual(
            manifest["actions"]["walking"]["expandedSequence"],
            [1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6],
        )
        self.assertEqual(
            manifest["actions"]["running"]["sourceType"],
            "backup-6frame-expanded",
        )
        self.assertEqual(
            manifest["actions"]["running"]["expandedSequence"],
            [1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6],
        )

    def test_ground_motion_frames_are_nonempty_and_bottom_anchored(self):
        for action_name in GROUND_ACTIONS:
            bboxes = []
            for frame_index in range(1, 13):
                frame_path = MOTION_PACK / action_name / f"frame-{frame_index:02d}.png"
                with Image.open(frame_path) as image:
                    self.assertEqual(image.size, (192, 208), frame_path)
                    bbox = image.convert("RGBA").getchannel("A").getbbox()
                    self.assertIsNotNone(bbox, frame_path)
                    bboxes.append(bbox)

            bottoms = [bbox[3] for bbox in bboxes]
            self.assertLessEqual(max(bottoms) - min(bottoms), 4, action_name)
            assert_no_wildly_cropped_frame(self, action_name, bboxes)


def read_manifest():
    return json.loads((MOTION_PACK / "frame-manifest.json").read_text(encoding="utf-8"))


def assert_no_wildly_cropped_frame(test_case, action_name, bboxes):
    widths = sorted(bbox[2] - bbox[0] for bbox in bboxes)
    heights = sorted(bbox[3] - bbox[1] for bbox in bboxes)
    median_width = widths[len(widths) // 2]
    median_height = heights[len(heights) // 2]

    for bbox in bboxes:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        test_case.assertGreaterEqual(width, median_width * 0.62, (action_name, bbox))
        test_case.assertGreaterEqual(height, median_height * 0.72, (action_name, bbox))

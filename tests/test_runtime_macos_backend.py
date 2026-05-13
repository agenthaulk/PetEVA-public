import unittest
from dataclasses import dataclass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime/peteva-runtime/src"))

from peteva_runtime.macos_backend import _reminder_args
from peteva_runtime.macos_backend import run_macos_backend
from peteva_runtime.motion import MotionSettings


@dataclass(frozen=True)
class FakeReminder:
    reminder_id: str
    enabled: bool
    interval_minutes: int
    display_seconds: int
    message: str


class MacOSBackendTest(unittest.TestCase):
    def test_reminder_args_are_passed_to_swift_backend(self):
        args = _reminder_args(
            (
                FakeReminder("water", True, 20, 55, "Drink water."),
                FakeReminder("activity", True, 30, 55, "Move around."),
            )
        )

        self.assertIn("--water-reminder-interval-minutes", args)
        self.assertIn("20", args)
        self.assertIn("--activity-reminder-interval-minutes", args)
        self.assertIn("30", args)
        self.assertIn("--water-reminder-display-seconds", args)
        self.assertIn("55", args)

    def test_motion_form_and_jump_height_args_are_passed_to_swift_backend(self):
        settings = MotionSettings(
            crawl_step_pixels=6,
            crawl_weight=1,
            jump_weight=2,
            jump_height_scale=1.2,
            direction_strategy="uniform",
        )

        # Keep this assertion small: run_macos_backend builds the command in one
        # place, and these flags are what the Swift side needs for crawl/jump.
        from peteva_runtime import macos_backend

        captured = {}

        def fake_build(project_root):
            return Path("/tmp/peteva-macos-runtime")

        def fake_run(command, check):
            captured["command"] = command

            class Result:
                returncode = 0

            return Result()

        original_build = macos_backend.build_macos_backend
        original_run = macos_backend.subprocess.run
        try:
            macos_backend.build_macos_backend = fake_build
            macos_backend.subprocess.run = fake_run
            run_macos_backend(
                project_root=Path("/tmp/project"),
                switch_file=Path("/tmp/switch.json"),
                pet_folder=Path("/tmp/pet"),
                unit_prefix="unit02",
                poll_ms=500,
                frame_ms=120,
                move_ms=120,
                scale=0.75,
                motion_settings=settings,
                reminders=(),
            )
        finally:
            macos_backend.build_macos_backend = original_build
            macos_backend.subprocess.run = original_run

        self.assertIn("--crawl-step-pixels", captured["command"])
        self.assertIn("6", captured["command"])
        self.assertIn("--crawl-weight", captured["command"])
        self.assertIn("1", captured["command"])
        self.assertIn("--jump-height-scale", captured["command"])
        self.assertIn("1.2", captured["command"])
        self.assertIn("--jump-weight", captured["command"])
        self.assertIn("2", captured["command"])
        self.assertIn("--direction-strategy", captured["command"])
        self.assertIn("uniform", captured["command"])
        self.assertIn("--unit-prefix", captured["command"])
        self.assertIn("unit02", captured["command"])


if __name__ == "__main__":
    unittest.main()

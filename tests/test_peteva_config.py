from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from peteva_config import load_project_config, read_runtime_config, read_sheet_config


class SheetConfigTest(unittest.TestCase):
    def test_reads_codex_sheet_contract(self):
        sheet = read_sheet_config(ROOT / "config/default.yaml")

        self.assertEqual(sheet.width, 1536)
        self.assertEqual(sheet.height, 1872)
        self.assertEqual(sheet.columns, 8)
        self.assertEqual(sheet.rows, 9)
        self.assertEqual(sheet.cell_width, 192)
        self.assertEqual(sheet.cell_height, 208)
        self.assertEqual(sheet.image_format, "webp")
        self.assertTrue(sheet.alpha)
        self.assertEqual(
            sheet.row_names,
            (
                "idle",
                "running-right",
                "running-left",
                "waving",
                "jumping",
                "failed",
                "waiting",
                "running",
                "review",
            ),
        )

    def test_reads_small_list_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "sample.yaml"
            config.write_text(
                "codexPet:\n"
                "  sheet:\n"
                "    width: 1536\n"
                "    height: 1872\n"
                "    columns: 8\n"
                "    rows: 2\n"
                "    cellWidth: 192\n"
                "    cellHeight: 208\n"
                "    format: webp\n"
                "    alpha: true\n"
                "  rows:\n"
                "    - idle\n"
                "    - running\n",
                encoding="utf-8",
            )

            sheet = read_sheet_config(config)

        self.assertEqual(sheet.width, 1536)
        self.assertTrue(sheet.alpha)
        self.assertEqual(sheet.row_names, ("idle", "running"))

    def test_keeps_hash_inside_quoted_color_values(self):
        config = load_project_config(ROOT / "config/default.yaml")

        self.assertEqual(config["units"]["eva-01"]["palette"]["primary"], "#3A245F")

    def test_rejects_row_count_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "bad.yaml"
            config.write_text(
                "codexPet:\n"
                "  sheet:\n"
                "    width: 1536\n"
                "    height: 1872\n"
                "    columns: 8\n"
                "    rows: 2\n"
                "    cellWidth: 192\n"
                "    cellHeight: 208\n"
                "    format: webp\n"
                "    alpha: true\n"
                "  rows:\n"
                "    - idle\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                read_sheet_config(config)


class RuntimeConfigTest(unittest.TestCase):
    def test_reads_runtime_motion_and_reminder_settings(self):
        runtime = read_runtime_config(ROOT / "config/default.yaml")

        self.assertEqual(runtime.pet.active_unit_id, "eva-02")
        self.assertEqual(runtime.window.poll_ms, 500)
        self.assertEqual(runtime.window.frame_ms, 120)
        self.assertEqual(runtime.window.move_ms, 120)
        self.assertEqual(runtime.window.scale, 0.75)
        self.assertEqual(runtime.motion.step_pixels, 8)
        self.assertEqual(runtime.motion.run_step_pixels, 14)
        self.assertEqual(runtime.motion.jump_step_pixels, 12)
        self.assertEqual(runtime.motion.crawl_step_pixels, 6)
        self.assertEqual(runtime.motion.jump_height_scale, 1.2)
        self.assertEqual(runtime.motion.direction_strategy, "uniform")
        self.assertEqual(runtime.motion.stationary_chance, 0.7)
        self.assertEqual(runtime.motion.horizontal_chance, 0.1)
        self.assertEqual(runtime.motion.vertical_chance, 0.9)
        self.assertEqual(runtime.motion.diagonal_chance, 0.2)
        self.assertEqual(runtime.motion.walk_weight, 6)
        self.assertEqual(runtime.motion.run_weight, 1)
        self.assertEqual(runtime.motion.crawl_weight, 1)
        self.assertEqual(runtime.motion.jump_weight, 2)
        self.assertEqual(runtime.motion.vertical_jump_weight, 1)
        self.assertEqual(runtime.motion.vertical_walk_weight, 4)
        self.assertEqual(runtime.motion.min_segment_ticks, 8)
        self.assertEqual(runtime.motion.max_segment_ticks, 20)
        self.assertEqual(runtime.reminders[0].reminder_id, "water")
        self.assertEqual(runtime.reminders[0].interval_minutes, 20)
        self.assertEqual(runtime.reminders[0].message, "该喝水了。")
        self.assertEqual(runtime.reminders[0].display_seconds, 55)
        self.assertEqual(runtime.reminders[1].reminder_id, "activity")
        self.assertEqual(runtime.reminders[1].interval_minutes, 30)
        self.assertEqual(runtime.reminders[1].message, "起来活动一下。")
        self.assertEqual(runtime.reminders[1].display_seconds, 55)
        self.assertLessEqual(runtime.reminders[0].display_seconds, 60)

    def test_reminder_default_display_seconds_are_optional_and_capped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "sample.yaml"
            config.write_text(
                "runtime:\n"
                "  reminders:\n"
                "    defaultDisplaySeconds: 90\n"
                "    water:\n"
                "      enabled: true\n"
                "      intervalMinutes: 20\n"
                "      message: Drink water.\n"
                "    activity:\n"
                "      enabled: true\n"
                "      intervalMinutes: 30\n"
                "      message: Move around.\n",
                encoding="utf-8",
            )

            runtime = read_runtime_config(config)

        self.assertEqual(runtime.reminders[0].display_seconds, 60)
        self.assertEqual(runtime.reminders[1].display_seconds, 60)

    def test_reminder_specific_display_seconds_override_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "sample.yaml"
            config.write_text(
                "runtime:\n"
                "  reminders:\n"
                "    defaultDisplaySeconds: 55\n"
                "    water:\n"
                "      enabled: true\n"
                "      intervalMinutes: 20\n"
                "      message: Drink water.\n"
                "      displaySeconds: 15\n"
                "    activity:\n"
                "      enabled: true\n"
                "      intervalMinutes: 30\n"
                "      message: Move around.\n",
                encoding="utf-8",
            )

            runtime = read_runtime_config(config)

        self.assertEqual(runtime.reminders[0].display_seconds, 15)
        self.assertEqual(runtime.reminders[1].display_seconds, 55)

    def test_rejects_inverted_motion_segment_bounds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "bad.yaml"
            config.write_text(
                "runtime:\n"
                "  motion:\n"
                "    minSegmentTicks: 20\n"
                "    maxSegmentTicks: 8\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                read_runtime_config(config)

    def test_rejects_unknown_motion_form(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "bad.yaml"
            config.write_text(
                "runtime:\n"
                "  motion:\n"
                "    forms:\n"
                "      moonwalk:\n"
                "        enabled: true\n"
                "        probabilityWeight: 1\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown movement forms"):
                read_runtime_config(config)

    def test_rejects_disabled_motion_forms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "bad.yaml"
            config.write_text(
                "runtime:\n"
                "  motion:\n"
                "    forms:\n"
                "      walk:\n"
                "        enabled: false\n"
                "      run:\n"
                "        enabled: false\n"
                "      crawl:\n"
                "        enabled: false\n"
                "      jump:\n"
                "        enabled: false\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "at least one"):
                read_runtime_config(config)

    def test_rejects_invalid_direction_strategy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "bad.yaml"
            config.write_text(
                "runtime:\n"
                "  motion:\n"
                "    directionStrategy: spiral\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "directionStrategy"):
                read_runtime_config(config)

    def test_rejects_unknown_active_unit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "bad.yaml"
            config.write_text(
                "project:\n"
                "  vertical_slice: eva-03\n"
                "units:\n"
                "  eva-01:\n"
                "    displayName: EVA Unit-01\n"
                "runtime:\n"
                "  pet:\n"
                "    activeUnit: eva-03\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "activeUnit"):
                read_runtime_config(config)


if __name__ == "__main__":
    unittest.main()

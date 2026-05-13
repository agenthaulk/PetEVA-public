from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "runtime/peteva-runtime/src"))

from peteva_runtime.assets import SheetLayout, find_project_root, load_spritesheet_frames, unit_asset_prefix
from peteva_runtime.lifecycle import (
    CodexDesktopStateProvider,
    LocalSwitchFileProvider,
    write_local_switch,
)


class LocalSwitchFileProviderTest(unittest.TestCase):
    def test_missing_file_is_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = LocalSwitchFileProvider(Path(temp_dir) / "missing.json", default_unit_id="eva-02")

            state = provider.read_state()

        self.assertFalse(state.enabled)
        self.assertEqual(state.unit_id, "eva-02")
        self.assertIn("missing", state.reason)

    def test_json_switch_enables_unit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_file = Path(temp_dir) / "pet-enabled.json"
            write_local_switch(switch_file, True, "eva-01")
            state = LocalSwitchFileProvider(switch_file).read_state()

        self.assertTrue(state.enabled)
        self.assertEqual(state.unit_id, "eva-01")

    def test_text_switch_disables_unit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_file = Path(temp_dir) / "pet-enabled.txt"
            switch_file.write_text("disabled\n", encoding="utf-8")
            state = LocalSwitchFileProvider(switch_file).read_state()

        self.assertFalse(state.enabled)
        self.assertIn("disabled", state.reason)

    def test_text_switch_uses_configured_default_unit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_file = Path(temp_dir) / "pet-enabled.txt"
            switch_file.write_text("enabled\n", encoding="utf-8")
            state = LocalSwitchFileProvider(switch_file, default_unit_id="eva-02").read_state()

        self.assertTrue(state.enabled)
        self.assertEqual(state.unit_id, "eva-02")

    def test_future_codex_provider_is_explicitly_disabled(self):
        state = CodexDesktopStateProvider().read_state()

        self.assertFalse(state.enabled)
        self.assertIn("not implemented", state.reason)


class RuntimeAssetsTest(unittest.TestCase):
    def test_finds_project_root_from_runtime_folder(self):
        root = find_project_root(ROOT / "runtime/peteva-runtime")

        self.assertEqual(root, ROOT)

    def test_sheet_layout_reads_shared_project_config(self):
        layout = SheetLayout.from_project_root(ROOT)

        self.assertEqual(layout.width, 1536)
        self.assertEqual(layout.height, 1872)
        self.assertEqual(layout.columns, 8)
        self.assertEqual(layout.rows, 9)
        self.assertEqual(layout.row_names[-1], "review")

    def test_loads_idle_frames_from_spritesheet(self):
        frames = load_spritesheet_frames(ROOT / "assets/codex-pets/eva-01/spritesheet.webp")

        self.assertEqual(len(frames), 8)
        self.assertEqual(frames[0].size, (192, 208))

    def test_unit_asset_prefix_maps_supported_eva_units(self):
        self.assertEqual(unit_asset_prefix("eva-00"), "unit00")
        self.assertEqual(unit_asset_prefix("eva-01"), "unit01")
        self.assertEqual(unit_asset_prefix("eva-02"), "unit02")

    def test_unit_asset_prefix_rejects_unknown_unit(self):
        with self.assertRaises(ValueError):
            unit_asset_prefix("eva-03")


if __name__ == "__main__":
    unittest.main()

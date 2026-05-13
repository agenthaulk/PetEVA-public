from pathlib import Path
import json
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_codex_pet import validate_manifest, validate_spritesheet
from peteva_config import read_sheet_config


class ManifestValidationTest(unittest.TestCase):
    def test_rejects_manifest_that_escapes_pet_folder(self):
        problems = []
        validate_manifest(
            {"displayName": "EVA Unit-01", "spritesheetPath": "../spritesheet.webp"},
            ROOT / "assets/codex-pets/eva-01",
            problems,
        )

        self.assertIn("manifest.spritesheetPath must stay inside the pet folder", problems)

    def test_accepts_basic_manifest_shape(self):
        problems = []
        validate_manifest(
            {"displayName": "EVA Unit-01", "spritesheetPath": "spritesheet.webp"},
            ROOT / "assets/codex-pets/eva-01",
            problems,
        )

        self.assertEqual(problems, [])


class SpritesheetValidationTest(unittest.TestCase):
    def test_rejects_wrong_dimensions(self):
        sheet = read_sheet_config(ROOT / "config/default.yaml")
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "bad.webp"
            Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(image_path, "WEBP")
            problems = []
            validate_spritesheet(image_path, sheet, problems)

        self.assertTrue(any("spritesheet dimensions" in problem for problem in problems))

    def test_current_manifest_is_json_when_present(self):
        manifest_path = ROOT / "assets/codex-pets/eva-01/pet.json"
        if manifest_path.exists():
            json.loads(manifest_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

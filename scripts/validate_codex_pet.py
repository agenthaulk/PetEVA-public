"""Validate the Unit-01 Codex pet package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from peteva_config import read_sheet_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a PetEVA Codex pet package.")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--pet-folder", default="assets/codex-pets/eva-01")
    args = parser.parse_args()

    project_root = Path.cwd()
    sheet = read_sheet_config(project_root / args.config)
    pet_folder = project_root / args.pet_folder
    manifest_path = pet_folder / "pet.json"
    spritesheet_path = pet_folder / "spritesheet.webp"

    problems: list[str] = []

    manifest = read_manifest(manifest_path, problems)
    if manifest:
        validate_manifest(manifest, pet_folder, problems)

    if spritesheet_path.exists():
        validate_spritesheet(spritesheet_path, sheet, problems)
    else:
        problems.append(f"Missing spritesheet: {spritesheet_path}")

    if problems:
        print("PetEVA validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("PetEVA validation passed:")
    print(f"- manifest: {manifest_path}")
    print(f"- spritesheet: {spritesheet_path}")
    print(f"- dimensions: {sheet.width} x {sheet.height}")
    print(f"- grid: {sheet.columns} columns x {sheet.rows} rows")
    return 0


def read_manifest(path: Path, problems: list[str]) -> dict[str, object] | None:
    if not path.exists():
        problems.append(f"Missing manifest: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        problems.append(f"Manifest is not valid JSON: {error}")
        return None


def validate_manifest(
    manifest: dict[str, object], pet_folder: Path, problems: list[str]
) -> None:
    display_name = manifest.get("displayName")
    spritesheet_path = manifest.get("spritesheetPath")

    if not isinstance(display_name, str) or not display_name.strip():
        problems.append("manifest.displayName must be a non-empty string")
    if not isinstance(spritesheet_path, str) or not spritesheet_path.strip():
        problems.append("manifest.spritesheetPath must be a non-empty string")
        return

    if Path(spritesheet_path).is_absolute() or ".." in Path(spritesheet_path).parts:
        problems.append("manifest.spritesheetPath must stay inside the pet folder")

    if "exPic" in spritesheet_path:
        problems.append("manifest must not reference reference-only exPic assets")

    expected = pet_folder / spritesheet_path
    if expected.name != "spritesheet.webp":
        problems.append("manifest.spritesheetPath should be spritesheet.webp")


def validate_spritesheet(path: Path, sheet, problems: list[str]) -> None:
    try:
        with Image.open(path) as image:
            image.load()
            size = image.size
            mode = image.mode
    except OSError as error:
        problems.append(f"Cannot read spritesheet: {error}")
        return

    if size != (sheet.width, sheet.height):
        problems.append(
            f"spritesheet dimensions are {size[0]} x {size[1]}, "
            f"expected {sheet.width} x {sheet.height}"
        )
    if mode not in {"RGBA", "LA"}:
        problems.append(f"spritesheet must have alpha; image mode is {mode}")

    expected_cell = (sheet.width // sheet.columns, sheet.height // sheet.rows)
    if expected_cell != (sheet.cell_width, sheet.cell_height):
        problems.append(
            f"grid math gives cell {expected_cell}, expected "
            f"{sheet.cell_width} x {sheet.cell_height}"
        )


if __name__ == "__main__":
    raise SystemExit(main())

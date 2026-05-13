"""Asset loading helpers for the lightweight runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None


@dataclass(frozen=True)
class SheetLayout:
    width: int
    height: int
    columns: int
    rows: int
    cell_width: int
    cell_height: int
    row_names: tuple[str, ...]

    @classmethod
    def from_project_root(cls, project_root: Path) -> "SheetLayout":
        config = _read_sheet_config(project_root)
        return cls(
            width=config.width,
            height=config.height,
            columns=config.columns,
            rows=config.rows,
            cell_width=config.cell_width,
            cell_height=config.cell_height,
            row_names=config.row_names,
        )

    def row_index(self, row_name: str) -> int:
        try:
            return self.row_names.index(row_name)
        except ValueError as error:
            known_rows = ", ".join(self.row_names)
            raise ValueError(f"unknown row name: {row_name}; expected one of {known_rows}") from error


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        config_path = candidate / "config" / "default.yaml"
        readme_path = candidate / "README.md"
        if config_path.exists() and readme_path.exists():
            return candidate

    return start.resolve()


def default_pet_folder(project_root: Path, unit_id: str = "eva-01") -> Path:
    return project_root / "assets" / "codex-pets" / unit_id


def unit_asset_prefix(unit_id: str) -> str:
    """Map repo unit ids like eva-02 to frame prefixes like unit02."""

    if not unit_id.startswith("eva-"):
        raise ValueError(f"unsupported unit id: {unit_id}")
    suffix = unit_id.removeprefix("eva-")
    if suffix not in {"00", "01", "02"}:
        raise ValueError(f"unsupported unit id: {unit_id}")
    return f"unit{suffix}"


def default_switch_file(project_root: Path) -> Path:
    return project_root / "runtime" / "peteva-runtime" / "state" / "pet-enabled.json"


def default_sheet_layout(project_root: Path) -> SheetLayout:
    return SheetLayout.from_project_root(project_root)


def load_spritesheet_frames(
    spritesheet_path: Path,
    row_name: str = "idle",
    layout: SheetLayout | None = None,
    project_root: Path | None = None,
) -> list[Image.Image]:
    if Image is None:
        raise RuntimeError("Pillow is not available in this Python runtime")

    if not spritesheet_path.exists():
        raise FileNotFoundError(f"spritesheet not found: {spritesheet_path}")

    if layout is None:
        root = project_root if project_root else find_project_root(spritesheet_path)
        layout = default_sheet_layout(root)

    atlas = Image.open(spritesheet_path).convert("RGBA")
    expected_size = (layout.width, layout.height)
    if atlas.size != expected_size:
        raise ValueError(f"spritesheet is {atlas.size}, expected {expected_size}")

    row_index = layout.row_index(row_name)
    frames: list[Image.Image] = []
    for column in range(layout.columns):
        left = column * layout.cell_width
        top = row_index * layout.cell_height
        box = (left, top, left + layout.cell_width, top + layout.cell_height)
        frames.append(atlas.crop(box))

    return frames


def _read_sheet_config(project_root: Path):
    scripts_path = project_root / "scripts"
    if str(scripts_path) not in sys.path:
        sys.path.insert(0, str(scripts_path))

    from peteva_config import read_sheet_config

    return read_sheet_config(project_root / "config" / "default.yaml")

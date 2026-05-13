"""Small config reader for PetEVA build scripts.

The project config is intentionally tiny, so this parser supports only the
YAML shapes used in config/default.yaml: nested maps, scalar strings, booleans,
integers, and simple lists. Keeping it local avoids adding a YAML dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SheetConfig:
    width: int
    height: int
    columns: int
    rows: int
    cell_width: int
    cell_height: int
    image_format: str
    alpha: bool
    row_names: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeWindowConfig:
    poll_ms: int
    frame_ms: int
    move_ms: int
    scale: float


@dataclass(frozen=True)
class RuntimePetConfig:
    active_unit_id: str


@dataclass(frozen=True)
class RuntimeMotionConfig:
    step_pixels: int
    run_step_pixels: int
    jump_step_pixels: int
    crawl_step_pixels: int
    jump_height_scale: float
    direction_strategy: str
    stationary_chance: float
    horizontal_chance: float
    vertical_chance: float
    diagonal_chance: float
    walk_weight: int
    run_weight: int
    crawl_weight: int
    jump_weight: int
    vertical_jump_weight: int
    vertical_walk_weight: int
    screen_margin: int
    min_segment_ticks: int
    max_segment_ticks: int


@dataclass(frozen=True)
class ReminderConfig:
    reminder_id: str
    enabled: bool
    interval_minutes: int
    display_seconds: int
    message: str

    @property
    def interval_ms(self) -> int:
        return self.interval_minutes * 60 * 1000

    @property
    def display_ms(self) -> int:
        return self.display_seconds * 1000


@dataclass(frozen=True)
class RuntimeConfig:
    pet: RuntimePetConfig
    window: RuntimeWindowConfig
    motion: RuntimeMotionConfig
    reminders: tuple[ReminderConfig, ...]


def load_project_config(config_path: Path) -> dict[str, Any]:
    """Read the small project YAML config into a nested dictionary."""

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line:
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]

        if stripped.startswith("- "):
            item = _parse_scalar(stripped[2:].strip())
            list_key = "__list__"
            parent.setdefault(list_key, []).append(item)
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)

    _replace_internal_lists(root)
    return root


def read_sheet_config(config_path: Path) -> SheetConfig:
    config = load_project_config(config_path)
    codex_pet = config["codexPet"]
    sheet = codex_pet["sheet"]
    row_names = tuple(str(row_name) for row_name in codex_pet["rows"])
    row_count = int(sheet["rows"])
    if len(row_names) != row_count:
        raise ValueError(
            f"config row count mismatch: sheet.rows={row_count}, rows={len(row_names)}"
        )

    return SheetConfig(
        width=int(sheet["width"]),
        height=int(sheet["height"]),
        columns=int(sheet["columns"]),
        rows=row_count,
        cell_width=int(sheet["cellWidth"]),
        cell_height=int(sheet["cellHeight"]),
        image_format=str(sheet["format"]),
        alpha=bool(sheet["alpha"]),
        row_names=row_names,
    )


def read_runtime_config(config_path: Path) -> RuntimeConfig:
    config = load_project_config(config_path)
    runtime = config.get("runtime", {})
    units = config.get("units", {})
    pet = runtime.get("pet", {})
    window = runtime.get("window", {})
    motion = runtime.get("motion", {})
    reminders = runtime.get("reminders", {})

    default_display_seconds = _read_default_reminder_display_seconds(reminders)
    min_segment_ticks = _positive_int(
        motion.get("minSegmentTicks", 8),
        "runtime.motion.minSegmentTicks",
    )
    max_segment_ticks = _positive_int(
        motion.get("maxSegmentTicks", 20),
        "runtime.motion.maxSegmentTicks",
    )
    if max_segment_ticks < min_segment_ticks:
        raise ValueError("runtime.motion.maxSegmentTicks must be >= minSegmentTicks")
    direction_strategy = _direction_strategy(
        motion.get("directionStrategy", "uniform"),
        "runtime.motion.directionStrategy",
    )
    form_weights = _read_motion_form_weights(motion)

    return RuntimeConfig(
        pet=RuntimePetConfig(
            active_unit_id=_unit_id(
                pet.get("activeUnit", config.get("project", {}).get("vertical_slice", "eva-01")),
                "runtime.pet.activeUnit",
                units,
            ),
        ),
        window=RuntimeWindowConfig(
            poll_ms=_positive_int(window.get("pollMs", 500), "runtime.window.pollMs"),
            frame_ms=_positive_int(window.get("frameMs", 120), "runtime.window.frameMs"),
            move_ms=_positive_int(window.get("moveMs", 120), "runtime.window.moveMs"),
            scale=_percent_to_scale(
                window.get("scalePercent", 75),
                "runtime.window.scalePercent",
            ),
        ),
        motion=RuntimeMotionConfig(
            step_pixels=_positive_int(
                motion.get("stepPixels", 4),
                "runtime.motion.stepPixels",
            ),
            run_step_pixels=_positive_int(
                motion.get("runStepPixels", 8),
                "runtime.motion.runStepPixels",
            ),
            jump_step_pixels=_positive_int(
                motion.get("jumpStepPixels", 5),
                "runtime.motion.jumpStepPixels",
            ),
            crawl_step_pixels=_positive_int(
                motion.get("crawlStepPixels", 3),
                "runtime.motion.crawlStepPixels",
            ),
            jump_height_scale=_percent_to_scale(
                motion.get("jumpHeightPercent", 120),
                "runtime.motion.jumpHeightPercent",
            ),
            direction_strategy=direction_strategy,
            stationary_chance=_percent_to_chance(
                motion.get("stationaryPercent", 70),
                "runtime.motion.stationaryPercent",
            ),
            horizontal_chance=_percent_to_chance(
                motion.get("horizontalPercent", 10),
                "runtime.motion.horizontalPercent",
            ),
            vertical_chance=_percent_to_chance(
                motion.get("verticalPercent", 90),
                "runtime.motion.verticalPercent",
            ),
            diagonal_chance=_percent_to_chance(
                motion.get("diagonalPercent", 20),
                "runtime.motion.diagonalPercent",
            ),
            walk_weight=form_weights["walk"],
            run_weight=form_weights["run"],
            crawl_weight=form_weights["crawl"],
            jump_weight=form_weights["jump"],
            vertical_jump_weight=_positive_int(
                motion.get("verticalJumpWeight", 1),
                "runtime.motion.verticalJumpWeight",
            ),
            vertical_walk_weight=_positive_int(
                motion.get("verticalWalkWeight", 4),
                "runtime.motion.verticalWalkWeight",
            ),
            screen_margin=_non_negative_int(
                motion.get("screenMargin", 8),
                "runtime.motion.screenMargin",
            ),
            min_segment_ticks=min_segment_ticks,
            max_segment_ticks=max_segment_ticks,
        ),
        reminders=tuple(
            _read_reminder_config(reminder_id, reminders, default_display_seconds)
            for reminder_id in ("water", "activity")
        ),
    )


def _read_reminder_config(
    reminder_id: str,
    reminders: dict[str, Any],
    default_display_seconds: int,
) -> ReminderConfig:
    reminder = reminders.get(reminder_id, {})
    if not isinstance(reminder, dict):
        raise ValueError(f"runtime.reminders.{reminder_id} must be a map")
    return ReminderConfig(
        reminder_id=reminder_id,
        enabled=bool(reminder.get("enabled", True)),
        interval_minutes=_positive_int(
            reminder.get("intervalMinutes", 20),
            f"runtime.reminders.{reminder_id}.intervalMinutes",
        ),
        display_seconds=_read_reminder_display_seconds(
            reminder,
            default_display_seconds,
            f"runtime.reminders.{reminder_id}.displaySeconds",
        ),
        message=str(reminder.get("message", reminder_id)),
    )


def _read_default_reminder_display_seconds(reminders: dict[str, Any]) -> int:
    # `displaySeconds` is the legacy global key. Prefer the clearer
    # `defaultDisplaySeconds`, but keep old configs readable.
    value = reminders.get("defaultDisplaySeconds", reminders.get("displaySeconds", 55))
    return _cap_reminder_display_seconds(value, "runtime.reminders.defaultDisplaySeconds")


def _read_reminder_display_seconds(
    reminder: dict[str, Any],
    default_display_seconds: int,
    field_name: str,
) -> int:
    value = reminder.get("displaySeconds")
    if value is None:
        return default_display_seconds
    return _cap_reminder_display_seconds(value, field_name)


def _cap_reminder_display_seconds(value: Any, field_name: str) -> int:
    return min(_positive_int(value, field_name), 60)


def _read_motion_form_weights(motion: dict[str, Any]) -> dict[str, int]:
    allowed = ("walk", "run", "crawl", "jump")
    legacy_defaults = {
        "walk": motion.get("walkWeight", 6),
        "run": motion.get("runWeight", 1),
        "crawl": motion.get("crawlWeight", 1),
        "jump": motion.get("jumpWeight", 2),
    }
    forms = motion.get("forms")
    if forms is None:
        weights = {
            name: _non_negative_int(value, f"runtime.motion.{name}Weight")
            for name, value in legacy_defaults.items()
        }
    else:
        if not isinstance(forms, dict):
            raise ValueError("runtime.motion.forms must be a map")
        unknown = sorted(set(forms.keys()) - set(allowed))
        if unknown:
            raise ValueError(f"runtime.motion.forms has unknown movement forms: {', '.join(unknown)}")

        weights = {}
        for name in allowed:
            form = forms.get(name, {})
            if not isinstance(form, dict):
                raise ValueError(f"runtime.motion.forms.{name} must be a map")
            enabled = bool(form.get("enabled", True))
            weight = _non_negative_int(
                form.get("probabilityWeight", legacy_defaults[name]),
                f"runtime.motion.forms.{name}.probabilityWeight",
            )
            weights[name] = weight if enabled else 0

    if sum(weights.values()) <= 0:
        raise ValueError("at least one runtime.motion.forms entry must be enabled with probabilityWeight > 0")
    return weights


def _positive_int(value: Any, field_name: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return number


def _non_negative_int(value: Any, field_name: str) -> int:
    number = int(value)
    if number < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return number


def _percent_to_chance(value: Any, field_name: str) -> float:
    percent = int(value)
    if percent < 0 or percent > 100:
        raise ValueError(f"{field_name} must be between 0 and 100")
    return percent / 100


def _percent_to_scale(value: Any, field_name: str) -> float:
    percent = _positive_int(value, field_name)
    return percent / 100


def _direction_strategy(value: Any, field_name: str) -> str:
    strategy = str(value)
    if strategy not in {"uniform", "legacyWeighted"}:
        raise ValueError(f"{field_name} must be uniform or legacyWeighted")
    return strategy


def _unit_id(value: Any, field_name: str, units: Any) -> str:
    unit_id = str(value)
    known_units = units if isinstance(units, dict) and units else {
        "eva-00": {},
        "eva-01": {},
        "eva-02": {},
    }
    if unit_id not in known_units:
        known = ", ".join(sorted(known_units.keys()))
        raise ValueError(f"{field_name} must reference a configured unit: {known}")
    return unit_id


def _parse_scalar(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value in {"true", "false"}:
        return value == "true"
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def _strip_comment(raw_line: str) -> str:
    in_quote = False
    quote_char = ""

    for index, character in enumerate(raw_line):
        if character in {'"', "'"}:
            if not in_quote:
                in_quote = True
                quote_char = character
            elif quote_char == character:
                in_quote = False
        elif character == "#" and not in_quote:
            return raw_line[:index]

    return raw_line


def _replace_internal_lists(node: Any) -> Any:
    if not isinstance(node, dict):
        return node

    for key, value in list(node.items()):
        if isinstance(value, dict):
            _replace_internal_lists(value)
            if set(value.keys()) == {"__list__"}:
                node[key] = value["__list__"]

    return node

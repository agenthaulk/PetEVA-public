"""Small movement rules for the desktop pet window."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol


class RandomSource(Protocol):
    def random(self) -> float:
        """Return a float in the half-open range [0.0, 1.0)."""

    def choice(self, values: list[int]) -> int:
        """Return one value from a list."""


@dataclass(frozen=True)
class MotionSettings:
    step_pixels: int = 8
    run_step_pixels: int = 14
    jump_step_pixels: int = 12
    crawl_step_pixels: int = 6
    jump_height_scale: float = 1.2
    direction_strategy: str = "uniform"
    stationary_chance: float = 0.7
    horizontal_chance: float = 0.1
    vertical_chance: float = 0.9
    diagonal_chance: float = 0.2
    walk_weight: int = 6
    run_weight: int = 1
    crawl_weight: int = 1
    jump_weight: int = 2
    vertical_jump_weight: int = 1
    vertical_walk_weight: int = 4
    screen_margin: int = 8
    min_segment_ticks: int = 8
    max_segment_ticks: int = 20


@dataclass(frozen=True)
class MovementStep:
    dx: int
    dy: int
    row_name: str
    movement_kind: str = "idle"


def choose_movement_step(random_source: RandomSource, settings: MotionSettings) -> MovementStep:
    """Choose one desktop movement segment.

    The default strategy is intentionally modular: choose a movement form from
    configured weights, then choose a direction vector and per-frame step from
    a uniform distribution. Legacy weighted direction selection remains
    available for existing configs.
    """

    if random_source.random() < settings.stationary_chance:
        return MovementStep(dx=0, dy=0, row_name="idle", movement_kind="idle")

    if settings.direction_strategy == "legacyWeighted":
        return _choose_legacy_weighted_step(random_source, settings)
    return _choose_uniform_step(random_source, settings)


def _choose_uniform_step(random_source: RandomSource, settings: MotionSettings) -> MovementStep:
    horizontal_primary = _choose_horizontal_primary(random_source, settings)
    movement_kind = _choose_uniform_movement_kind(random_source, settings, horizontal_primary)
    step_pixels = _uniform_step_pixels(random_source, _step_pixels_for_kind(settings, movement_kind))
    dx_multiplier, dy_multiplier = _uniform_direction(random_source, movement_kind != "jump")
    dx = dx_multiplier * step_pixels
    dy = dy_multiplier * step_pixels
    return MovementStep(
        dx=dx,
        dy=dy,
        row_name=row_name_for_movement(dx, dy, movement_kind),
        movement_kind=movement_kind,
    )


def _choose_legacy_weighted_step(
    random_source: RandomSource,
    settings: MotionSettings,
) -> MovementStep:
    horizontal_primary = _choose_horizontal_primary(random_source, settings)
    diagonal_active = random_source.random() < settings.diagonal_chance
    vertical_candidate = (not horizontal_primary) or diagonal_active
    vertical_jump = vertical_candidate and _choose_vertical_jump(random_source, settings)
    movement_kind = "jump" if vertical_jump else _choose_ground_movement_kind(random_source, settings)
    step_pixels = _step_pixels_for_kind(settings, movement_kind)

    dx = 0
    dy = 0
    if horizontal_primary:
        dx = _signed_step(random_source, step_pixels)
        if diagonal_active and vertical_jump:
            dy = _signed_step(random_source, step_pixels)
    else:
        if vertical_jump:
            dy = _signed_step(random_source, step_pixels)
        else:
            dx = _signed_step(random_source, settings.step_pixels)
        if diagonal_active and vertical_jump:
            dx = _signed_step(random_source, step_pixels)
    return MovementStep(dx=dx, dy=dy, row_name=row_name_for_movement(dx, dy, movement_kind), movement_kind=movement_kind)


def row_name_for_movement(dx: int, dy: int, movement_kind: str = "run") -> str:
    if movement_kind == "jump":
        if dx > 0 and dy != 0:
            return "jumping-right"
        if dx < 0 and dy != 0:
            return "jumping-left"
        return "jumping"
    if dx > 0:
        if movement_kind == "crawl":
            return "crawling-right"
        return "running-right" if movement_kind == "run" else "walking-right"
    if dx < 0:
        if movement_kind == "crawl":
            return "crawling-left"
        return "running-left" if movement_kind == "run" else "walking-left"
    if dy != 0:
        return "jumping"
    return "idle"


def movement_delta_for_phase(
    step: MovementStep,
    phase: int,
    frame_count: int = 8,
    jump_height_pixels: int = 0,
) -> tuple[int, int]:
    """Return the synchronized movement impulse for one animation phase."""

    if step.dx == 0 and step.dy == 0:
        return 0, 0

    normalized_phase = phase % frame_count
    if step.movement_kind == "jump" and jump_height_pixels > 0:
        dx = step.dx if normalized_phase in _propulsive_phases("jump", frame_count) else 0
        dy = _jump_arc_delta(normalized_phase, frame_count, jump_height_pixels)
        return dx, dy

    return _phase_delta(
        step,
        normalized_phase,
        _propulsive_phases(step.movement_kind, frame_count),
    )


def clamp_position(
    x: int,
    y: int,
    screen_width: int,
    screen_height: int,
    window_width: int,
    window_height: int,
    margin: int,
) -> tuple[int, int]:
    min_x = margin
    min_y = margin
    max_x = max(min_x, screen_width - window_width - margin)
    max_y = max(min_y, screen_height - window_height - margin)
    return min(max(x, min_x), max_x), min(max(y, min_y), max_y)


def redirect_step_away_from_edges(
    step: MovementStep,
    x: int,
    y: int,
    screen_width: int,
    screen_height: int,
    window_width: int,
    window_height: int,
    margin: int,
) -> MovementStep:
    """Flip a new movement segment inward when it starts against a screen edge."""

    dx = step.dx
    dy = step.dy
    min_x = margin
    min_y = margin
    max_x = max(min_x, screen_width - window_width - margin)
    max_y = max(min_y, screen_height - window_height - margin)

    if x <= min_x and dx < 0:
        dx = abs(dx)
    elif x >= max_x and dx > 0:
        dx = -abs(dx)

    if y <= min_y and dy < 0:
        dy = abs(dy)
    elif y >= max_y and dy > 0:
        dy = -abs(dy)

    if dx == step.dx and dy == step.dy:
        return step

    return MovementStep(
        dx=dx,
        dy=dy,
        row_name=row_name_for_movement(dx, dy, step.movement_kind),
        movement_kind=step.movement_kind,
    )


def _signed_step(random_source: RandomSource, step_pixels: int) -> int:
    return random_source.choice([-step_pixels, step_pixels])


def _uniform_step_pixels(random_source: RandomSource, step_pixels: int) -> int:
    lower = max(1, math.ceil(step_pixels * 0.7))
    span = max(1, step_pixels - lower + 1)
    return lower + min(span - 1, int(random_source.random() * span))


def _uniform_direction(random_source: RandomSource, horizontal_primary: bool) -> tuple[int, int]:
    if horizontal_primary:
        directions = ((-1, 0), (1, 0))
    else:
        directions = ((0, -1), (0, 1))
    index = min(len(directions) - 1, int(random_source.random() * len(directions)))
    return directions[index]


def _choose_horizontal_primary(random_source: RandomSource, settings: MotionSettings) -> bool:
    total_chance = settings.horizontal_chance + settings.vertical_chance
    if total_chance <= 0:
        return True
    return random_source.random() < settings.horizontal_chance / total_chance


def _choose_movement_kind(random_source: RandomSource, settings: MotionSettings) -> str:
    return _weighted_kind(
        random_source,
        ("walk", settings.walk_weight),
        ("run", settings.run_weight),
        ("crawl", settings.crawl_weight),
        ("jump", settings.jump_weight),
    )


def _choose_uniform_movement_kind(
    random_source: RandomSource,
    settings: MotionSettings,
    horizontal_primary: bool,
) -> str:
    if horizontal_primary:
        if _ground_weight_total(settings) > 0:
            return _choose_ground_movement_kind(random_source, settings)
        return "jump"

    if settings.jump_weight > 0:
        return "jump"
    return _choose_ground_movement_kind(random_source, settings)


def _choose_ground_movement_kind(random_source: RandomSource, settings: MotionSettings) -> str:
    return _weighted_kind(
        random_source,
        ("walk", settings.walk_weight),
        ("run", settings.run_weight),
        ("crawl", settings.crawl_weight),
    )


def _ground_weight_total(settings: MotionSettings) -> int:
    return max(0, settings.walk_weight) + max(0, settings.run_weight) + max(0, settings.crawl_weight)


def _choose_vertical_jump(random_source: RandomSource, settings: MotionSettings) -> bool:
    kind = _weighted_kind(
        random_source,
        ("jump", settings.vertical_jump_weight),
        ("walk", settings.vertical_walk_weight),
    )
    return kind == "jump"


def _weighted_kind(random_source: RandomSource, *options: tuple[str, int]) -> str:
    total = sum(max(0, weight) for _, weight in options)
    if total <= 0:
        return options[0][0]

    roll = random_source.random() * total
    cursor = 0
    for name, weight in options:
        cursor += max(0, weight)
        if roll < cursor:
            return name
    return options[-1][0]


def _step_pixels_for_kind(settings: MotionSettings, movement_kind: str) -> int:
    if movement_kind == "run":
        return settings.run_step_pixels
    if movement_kind == "jump":
        return settings.jump_step_pixels
    if movement_kind == "crawl":
        return settings.crawl_step_pixels
    return settings.step_pixels


def _propulsive_phases(movement_kind: str, frame_count: int) -> frozenset[int]:
    if frame_count <= 1:
        return frozenset({0})

    last_phase = frame_count - 1
    if movement_kind == "jump":
        return frozenset(range(1, last_phase))
    if movement_kind == "run":
        return frozenset(phase for phase in range(frame_count) if phase % 3 != 2)
    if movement_kind == "crawl":
        return frozenset(range(1, last_phase))
    return frozenset(phase for phase in range(frame_count) if phase % 2 == 1)


def _phase_delta(
    step: MovementStep,
    phase: int,
    propulsive_phases: frozenset[int],
) -> tuple[int, int]:
    if phase in propulsive_phases:
        return step.dx, step.dy
    return 0, 0


def _jump_arc_delta(phase: int, frame_count: int, jump_height_pixels: int) -> int:
    if frame_count <= 1:
        return 0

    previous_phase = phase - 1 if phase > 0 else frame_count - 1
    current_offset = _jump_arc_offset(phase, frame_count, jump_height_pixels)
    previous_offset = _jump_arc_offset(previous_phase, frame_count, jump_height_pixels)
    return current_offset - previous_offset


def _jump_arc_offset(phase: int, frame_count: int, jump_height_pixels: int) -> int:
    if frame_count <= 1:
        return 0
    progress = phase / (frame_count - 1)
    return -round(jump_height_pixels * math.sin(math.pi * progress))

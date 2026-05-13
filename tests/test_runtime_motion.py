import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "runtime/peteva-runtime/src"))

from peteva_runtime.motion import (
    MotionSettings,
    choose_movement_step,
    clamp_position,
    movement_delta_for_phase,
    redirect_step_away_from_edges,
    row_name_for_movement,
)


class FakeRandom:
    def __init__(self, random_values, choices):
        self.random_values = list(random_values)
        self.choices = list(choices)

    def random(self) -> float:
        return self.random_values.pop(0)

    def choice(self, values: list[int]) -> int:
        value = self.choices.pop(0)
        self.assert_value_is_allowed(value, values)
        return value

    def assert_value_is_allowed(self, value: int, values: list[int]) -> None:
        if value not in values:
            raise AssertionError(f"{value} is not in {values}")


def choose_step(dx: int, dy: int, row_name: str, movement_kind: str):
    from peteva_runtime.motion import MovementStep

    return MovementStep(dx=dx, dy=dy, row_name=row_name, movement_kind=movement_kind)


class RuntimeMotionTest(unittest.TestCase):
    def test_default_motion_ratio_is_vertical_first(self):
        settings = MotionSettings()

        self.assertEqual(settings.stationary_chance, 0.7)
        self.assertEqual(settings.horizontal_chance, 0.1)
        self.assertEqual(settings.vertical_chance, 0.9)
        self.assertEqual(settings.step_pixels, 8)
        self.assertEqual(settings.run_step_pixels, 14)
        self.assertEqual(settings.jump_step_pixels, 12)
        self.assertEqual(settings.crawl_step_pixels, 6)
        self.assertEqual(settings.jump_height_scale, 1.2)
        self.assertEqual(settings.direction_strategy, "uniform")
        self.assertEqual(settings.walk_weight, 6)
        self.assertEqual(settings.run_weight, 1)
        self.assertEqual(settings.crawl_weight, 1)
        self.assertEqual(settings.jump_weight, 2)
        self.assertEqual(settings.vertical_jump_weight, 1)
        self.assertEqual(settings.vertical_walk_weight, 4)
        self.assertEqual(settings.min_segment_ticks, 8)
        self.assertEqual(settings.max_segment_ticks, 20)

    def test_horizontal_walk_uses_walking_row_by_default(self):
        random_source = FakeRandom(random_values=[0.9, 0.05, 0.1, 0.99, 0.9], choices=[])

        step = choose_movement_step(random_source, MotionSettings())

        self.assertEqual(step.dx, 8)
        self.assertEqual(step.dy, 0)
        self.assertEqual(step.row_name, "walking-right")
        self.assertEqual(step.movement_kind, "walk")

    def test_horizontal_movement_can_use_run_row(self):
        random_source = FakeRandom(random_values=[0.9, 0.05, 0.78, 0.99, 0.9], choices=[])

        step = choose_movement_step(random_source, MotionSettings())

        self.assertEqual(step.dx, 14)
        self.assertEqual(step.dy, 0)
        self.assertEqual(step.row_name, "running-right")
        self.assertEqual(step.movement_kind, "run")

    def test_horizontal_movement_can_use_crawl_row(self):
        random_source = FakeRandom(random_values=[0.9, 0.05, 0.95, 0.99, 0.9], choices=[])

        step = choose_movement_step(random_source, MotionSettings())

        self.assertEqual(step.dx, 6)
        self.assertEqual(step.dy, 0)
        self.assertEqual(step.row_name, "crawling-right")
        self.assertEqual(step.movement_kind, "crawl")

    def test_vertical_only_movement_uses_jumping_row(self):
        random_source = FakeRandom(random_values=[0.9, 0.5, 0.99, 0.9], choices=[])

        step = choose_movement_step(random_source, MotionSettings())

        self.assertEqual(step.dx, 0)
        self.assertEqual(step.dy, 12)
        self.assertEqual(step.row_name, "jumping")
        self.assertEqual(step.movement_kind, "jump")

    def test_uniform_vertical_direction_can_move_up(self):
        random_source = FakeRandom(random_values=[0.9, 0.5, 0.99, 0.1], choices=[])

        step = choose_movement_step(random_source, MotionSettings())

        self.assertEqual(step.dx, 0)
        self.assertEqual(step.dy, -12)
        self.assertEqual(step.row_name, "jumping")
        self.assertEqual(step.movement_kind, "jump")

    def test_legacy_vertical_candidate_walk_has_no_vertical_vector(self):
        random_source = FakeRandom(random_values=[0.9, 0.9, 0.9, 0.9, 0.1], choices=[8])

        step = choose_movement_step(
            random_source,
            MotionSettings(direction_strategy="legacyWeighted"),
        )

        self.assertEqual(step.dx, 8)
        self.assertEqual(step.dy, 0)
        self.assertEqual(step.row_name, "walking-right")
        self.assertEqual(step.movement_kind, "walk")

    def test_stationary_roll_returns_idle_step(self):
        random_source = FakeRandom(random_values=[0.1], choices=[])

        step = choose_movement_step(random_source, MotionSettings(step_pixels=10))

        self.assertEqual(step.dx, 0)
        self.assertEqual(step.dy, 0)
        self.assertEqual(step.row_name, "idle")

    def test_row_name_for_movement(self):
        self.assertEqual(row_name_for_movement(10, 0), "running-right")
        self.assertEqual(row_name_for_movement(-10, 0), "running-left")
        self.assertEqual(row_name_for_movement(10, 0, "walk"), "walking-right")
        self.assertEqual(row_name_for_movement(-10, 0, "walk"), "walking-left")
        self.assertEqual(row_name_for_movement(10, 0, "crawl"), "crawling-right")
        self.assertEqual(row_name_for_movement(-10, 0, "crawl"), "crawling-left")
        self.assertEqual(row_name_for_movement(0, 10, "jump"), "jumping")
        self.assertEqual(row_name_for_movement(10, 10, "jump"), "jumping-right")
        self.assertEqual(row_name_for_movement(-10, 10, "jump"), "jumping-left")
        self.assertEqual(row_name_for_movement(0, 10, "walk"), "jumping")
        self.assertEqual(row_name_for_movement(0, 0), "idle")

    def test_walk_delta_moves_only_on_footfall_phases(self):
        step = choose_step(dx=8, dy=0, row_name="walking-right", movement_kind="walk")

        self.assertEqual(movement_delta_for_phase(step, 0), (0, 0))
        self.assertEqual(movement_delta_for_phase(step, 1), (8, 0))
        self.assertEqual(movement_delta_for_phase(step, 5, frame_count=12), (8, 0))

    def test_jump_delta_uses_full_height_arc_and_returns_to_baseline(self):
        step = choose_step(dx=12, dy=-12, row_name="jumping", movement_kind="jump")

        deltas = [
            movement_delta_for_phase(step, phase, frame_count=12, jump_height_pixels=120)
            for phase in range(12)
        ]

        self.assertEqual(deltas[0], (0, 0))
        self.assertLess(deltas[1][1], 0)
        self.assertGreater(deltas[-1][1], 0)
        self.assertEqual(sum(dy for _, dy in deltas), 0)
        self.assertEqual(max(-sum(dy for _, dy in deltas[: phase + 1]) for phase in range(12)), 119)

    def test_crawl_delta_uses_middle_motion_phases(self):
        step = choose_step(dx=6, dy=0, row_name="crawling-right", movement_kind="crawl")

        self.assertEqual(movement_delta_for_phase(step, 0, frame_count=12), (0, 0))
        self.assertEqual(movement_delta_for_phase(step, 2, frame_count=12), (6, 0))
        self.assertEqual(movement_delta_for_phase(step, 11, frame_count=12), (0, 0))

    def test_position_clamps_to_screen_with_margin(self):
        x, y = clamp_position(
            x=500,
            y=-20,
            screen_width=300,
            screen_height=200,
            window_width=50,
            window_height=40,
            margin=8,
        )

        self.assertEqual(x, 242)
        self.assertEqual(y, 8)

    def test_new_step_flips_inward_when_starting_on_right_edge(self):
        step = choose_step(dx=8, dy=0, row_name="walking-right", movement_kind="walk")

        redirected = redirect_step_away_from_edges(
            step=step,
            x=242,
            y=30,
            screen_width=400,
            screen_height=300,
            window_width=150,
            window_height=120,
            margin=8,
        )

        self.assertEqual(redirected.dx, -8)
        self.assertEqual(redirected.row_name, "walking-left")


if __name__ == "__main__":
    unittest.main()

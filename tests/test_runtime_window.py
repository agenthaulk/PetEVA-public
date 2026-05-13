import unittest
from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "runtime/peteva-runtime/src"))

from peteva_runtime.motion import MovementStep
from peteva_runtime.window import (
    MOTION_PACK_FRAME_COUNT,
    MOTION_PACK_FOLDER_TEMPLATE,
    MOTION_PACK_ROWS,
    PetWindow,
    TRANSPARENT_COLOR,
)


class FakeFrame:
    def __init__(self, width=144, height=156):
        self._width = width
        self._height = height

    def width(self):
        return self._width

    def height(self):
        return self._height


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def delete(self, tag):
        self.calls.append(("delete", tag))

    def create_image(self, x, y, anchor, image, tags):
        self.calls.append(
            ("create_image", x, y, anchor, image, tags),
        )


class FakeRoot:
    def __init__(self):
        self.attributes = []
        self.after_calls = []
        self.geometry_calls = []
        self.pointer_x = 500
        self.pointer_y = 500

    def wm_attributes(self, *args):
        self.attributes.append(args)

    def after(self, milliseconds, callback):
        self.after_calls.append((milliseconds, callback.__name__))

    def update_idletasks(self):
        pass

    def winfo_x(self):
        return 20

    def winfo_y(self):
        return 30

    def winfo_screenwidth(self):
        return 400

    def winfo_screenheight(self):
        return 300

    def geometry(self, value):
        self.geometry_calls.append(value)

    def winfo_pointerx(self):
        return self.pointer_x

    def winfo_pointery(self):
        return self.pointer_y

    def winfo_rootx(self):
        return 10

    def winfo_rooty(self):
        return 10

    def winfo_width(self):
        return 100

    def winfo_height(self):
        return 100


class FakeToolbar:
    def __init__(self):
        self.calls = []

    def place(self, **kwargs):
        self.calls.append(("place", kwargs))

    def lift(self):
        self.calls.append(("lift",))

    def place_forget(self):
        self.calls.append(("place_forget",))


class FakeReminder:
    enabled = True
    interval_ms = 1_200_000
    display_ms = 90_000
    message = "Drink water."


class FakeReminderLabel:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(("configure", kwargs))

    def place(self, **kwargs):
        self.calls.append(("place", kwargs))

    def lift(self):
        self.calls.append(("lift",))

    def place_forget(self):
        self.calls.append(("place_forget",))


class RuntimeWindowTest(unittest.TestCase):
    def test_motion_pack_has_twelve_frames_for_each_runtime_action(self):
        for unit_id, unit_prefix in (("eva-01", "unit01"), ("eva-02", "unit02")):
            frames_folder = ROOT / f"assets/codex-pets/{unit_id}/source/frames"
            motion_pack_folder = MOTION_PACK_FOLDER_TEMPLATE.format(unit_prefix=unit_prefix)

            for action_name, _ in set(MOTION_PACK_ROWS.values()):
                action_folder = frames_folder / motion_pack_folder / action_name
                frame_paths = [
                    action_folder / f"frame-{index:02d}.png"
                    for index in range(1, MOTION_PACK_FRAME_COUNT + 1)
                ]

                self.assertTrue(
                    all(frame_path.exists() for frame_path in frame_paths),
                    f"{unit_id} {action_name}",
                )

    def test_loads_unit02_motion_row_with_unit_prefix(self):
        pet_window = PetWindow.__new__(PetWindow)
        pet_window.spritesheet_path = ROOT / "assets/codex-pets/eva-02/spritesheet.webp"
        pet_window.unit_prefix = "unit02"
        fallback = [Image.new("RGBA", (192, 208), (0, 0, 0, 0))]

        frames = PetWindow._load_motion_row_or_fallback(
            pet_window,
            "walking-right",
            fallback,
        )

        self.assertEqual(len(frames), 12)
        self.assertEqual(frames[0].size, (192, 208))

    def test_transparency_attributes_use_color_key(self):
        pet_window = PetWindow.__new__(PetWindow)
        pet_window.root = FakeRoot()

        PetWindow._apply_window_transparency(pet_window)

        self.assertIn(("-transparentcolor", TRANSPARENT_COLOR), pet_window.root.attributes)
        self.assertIn(("-alpha", 1.0), pet_window.root.attributes)

    def test_tick_frame_clears_previous_sprite_before_drawing(self):
        pet_window = PetWindow.__new__(PetWindow)
        pet_window.canvas = FakeCanvas()
        pet_window.root = FakeRoot()
        pet_window.current_row_name = "idle"
        pet_window.frame_index = 0
        pet_window.rendered_frame_phase = 0
        pet_window.waiting_for_segment_frame = False
        pet_window.frame_ms = 140
        first_frame = FakeFrame()
        pet_window.tk_frames_by_row = {"idle": [first_frame]}

        PetWindow._tick_frame(pet_window)

        self.assertEqual(pet_window.canvas.calls[0], ("delete", "pet-sprite"))
        self.assertEqual(
            pet_window.canvas.calls[1],
            ("create_image", 0, 0, "nw", first_frame, "pet-sprite"),
        )
        self.assertEqual(pet_window.root.after_calls, [(140, "_tick_frame")])

    def test_toolbar_shows_and_hides_on_pointer_bounds(self):
        pet_window = PetWindow.__new__(PetWindow)
        pet_window.root = FakeRoot()
        pet_window.toolbar = FakeToolbar()

        PetWindow._show_toolbar(pet_window)
        PetWindow._hide_toolbar_if_pointer_left(pet_window)

        self.assertEqual(pet_window.toolbar.calls[0], ("place", {"x": 4, "y": 4}))
        self.assertEqual(pet_window.toolbar.calls[1], ("lift",))
        self.assertEqual(pet_window.toolbar.calls[2], ("place_forget",))

    def test_reminder_display_is_capped_at_one_minute(self):
        pet_window = PetWindow.__new__(PetWindow)
        pet_window.root = FakeRoot()
        pet_window.reminder_label = FakeReminderLabel()
        pet_window.reminder_version = 0

        PetWindow._show_reminder(pet_window, FakeReminder())

        self.assertEqual(
            pet_window.reminder_label.calls[0],
            ("configure", {"text": "Drink water."}),
        )
        self.assertEqual(pet_window.root.after_calls[0][0], 60_000)
        self.assertEqual(pet_window.root.after_calls[1][0], 1_200_000)

    def test_movement_uses_rendered_phase_not_next_frame_counter(self):
        pet_window = PetWindow.__new__(PetWindow)
        pet_window.canvas = FakeCanvas()
        pet_window.root = FakeRoot()
        pet_window.frame_index = 4
        pet_window.rendered_frame_phase = 0
        pet_window.waiting_for_segment_frame = False
        pet_window.frame_ms = 120
        pet_window.move_ms = 120
        pet_window.is_dragging = False
        pet_window.current_row_name = "walking-right"
        pet_window.current_movement_step = MovementStep(
            dx=4,
            dy=0,
            row_name="walking-right",
            movement_kind="walk",
        )
        pet_window.movement_ticks_remaining = 1
        pet_window.motion_settings = type(
            "Settings",
            (),
            {"screen_margin": 8, "jump_height_scale": 1.2},
        )()
        frames = [FakeFrame() for _ in range(8)]
        pet_window.tk_frames_by_row = {"walking-right": frames, "idle": frames}

        PetWindow._tick_frame(pet_window)
        PetWindow._tick_movement(pet_window)

        self.assertEqual(pet_window.root.geometry_calls, [])
        self.assertEqual(pet_window.movement_phase, 4)
        self.assertEqual(pet_window.frame_index, 5)

    def test_new_movement_segment_waits_until_first_frame_renders(self):
        class OneStepRandom:
            def random(self):
                return 0.9

            def choice(self, values):
                return values[-1]

            def randint(self, start, end):
                return start

        pet_window = PetWindow.__new__(PetWindow)
        pet_window.root = FakeRoot()
        pet_window.frame_index = 6
        pet_window.rendered_frame_phase = 6
        pet_window.waiting_for_segment_frame = False
        pet_window.move_ms = 120
        pet_window.is_dragging = False
        pet_window.current_row_name = "idle"
        pet_window.current_movement_step = None
        pet_window.movement_ticks_remaining = 0
        pet_window.random_source = OneStepRandom()
        pet_window.motion_settings = type(
            "Settings",
            (),
            {
                "step_pixels": 8,
                "run_step_pixels": 14,
                "jump_step_pixels": 12,
                "crawl_step_pixels": 6,
                "jump_height_scale": 1.2,
                "direction_strategy": "uniform",
                "stationary_chance": 0.7,
                "horizontal_chance": 1.0,
                "vertical_chance": 0.0,
                "diagonal_chance": 0.2,
                "walk_weight": 1,
                "run_weight": 0,
                "crawl_weight": 0,
                "jump_weight": 0,
                "vertical_jump_weight": 1,
                "vertical_walk_weight": 4,
                "screen_margin": 8,
                "min_segment_ticks": 8,
                "max_segment_ticks": 20,
            },
        )()
        frames = [FakeFrame() for _ in range(8)]
        pet_window.tk_frames_by_row = {"walking-right": frames, "idle": frames}

        PetWindow._tick_movement(pet_window)

        self.assertEqual(pet_window.frame_index, 0)
        self.assertTrue(pet_window.waiting_for_segment_frame)
        self.assertEqual(pet_window.root.geometry_calls, [])
        self.assertEqual(pet_window.movement_ticks_remaining, 8)

        pet_window.canvas = FakeCanvas()
        pet_window.frame_ms = 120
        PetWindow._tick_frame(pet_window)
        PetWindow._tick_movement(pet_window)

        self.assertFalse(pet_window.waiting_for_segment_frame)
        self.assertEqual(pet_window.rendered_frame_phase, 0)
        self.assertEqual(pet_window.root.geometry_calls, [])
        self.assertEqual(pet_window.movement_ticks_remaining, 7)


if __name__ == "__main__":
    unittest.main()

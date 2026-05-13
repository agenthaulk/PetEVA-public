"""Small Tkinter desktop window for PetEVA."""

from __future__ import annotations

from pathlib import Path
import random

try:
    import tkinter as tk
except ModuleNotFoundError:
    tk = None

try:
    from PIL import Image, ImageOps, ImageTk
except ModuleNotFoundError:
    Image = None
    ImageOps = None
    ImageTk = None

from .assets import load_spritesheet_frames
from .lifecycle import PetStateProvider
from .motion import (
    MovementStep,
    MotionSettings,
    choose_movement_step,
    clamp_position,
    movement_delta_for_phase,
    redirect_step_away_from_edges,
)


TRANSPARENT_COLOR = "#010203"
TOOLBAR_BACKGROUND = "#1f2329"
TOOLBAR_FOREGROUND = "#f4f7fb"
REMINDER_BACKGROUND = "#101014"
REMINDER_FOREGROUND = "#f4f7fb"
MOTION_PACK_FOLDER_TEMPLATE = "2026-05-13-{unit_prefix}-motion-12frame/runtime-12frame-clean"
MOTION_PACK_ROWS = {
    "walking-right": ("walking", True),
    "walking-left": ("walking", False),
    "running-right": ("running", True),
    "running-left": ("running", False),
    "crawling-right": ("crawling", True),
    "crawling-left": ("crawling", False),
    "jumping": ("vertical-jump", False),
    "jumping-right": ("diagonal-jump-right", False),
    "jumping-left": ("diagonal-jump", False),
}
MOTION_PACK_FRAME_COUNT = 12


class PetWindow:
    def __init__(
        self,
        provider: PetStateProvider,
        spritesheet_path: Path,
        poll_ms: int = 500,
        frame_ms: int = 120,
        move_ms: int = 120,
        scale: float = 0.75,
        step_pixels: int = 4,
        motion_settings: MotionSettings | None = None,
        reminders: tuple[object, ...] = (),
        unit_prefix: str = "unit01",
    ):
        self.provider = provider
        self.spritesheet_path = spritesheet_path
        self.poll_ms = poll_ms
        self.frame_ms = frame_ms
        self.move_ms = move_ms
        self.scale = scale
        self.motion_settings = motion_settings or MotionSettings(step_pixels=step_pixels)
        self.reminders = reminders
        self.unit_prefix = unit_prefix
        self.reminder_version = 0
        self.random_source = random.Random()

        self.frame_index = 0
        self.current_row_name = "idle"
        self.raw_frames_by_row: dict[str, list[Image.Image]] = {}
        self.tk_frames_by_row: dict[str, list[ImageTk.PhotoImage]] = {}
        self.current_movement_step: MovementStep | None = None
        self.movement_ticks_remaining = 0
        self.movement_phase = 0
        self.rendered_frame_phase = 0
        self.waiting_for_segment_frame = False

        if tk is None:
            raise RuntimeError("Tkinter is not available in this Python runtime")
        if Image is None or ImageOps is None or ImageTk is None:
            raise RuntimeError("Pillow is not available in this Python runtime")
        self.root = tk.Tk()
        self.root.title("PetEVA")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self._apply_window_transparency()

        self.canvas = tk.Canvas(
            self.root,
            width=1,
            height=1,
            borderwidth=0,
            highlightthickness=0,
            bg=TRANSPARENT_COLOR,
        )
        self.canvas.pack()
        self._bind_pointer_events(self.canvas)
        self._bind_pointer_events(self.root)

        self.toolbar = self._build_hover_toolbar()
        self._bind_hover_events(self.toolbar)
        self.toolbar.place_forget()
        self.reminder_label = self._build_reminder_label()
        self.reminder_label.place_forget()

        self.drag_x = 0
        self.drag_y = 0
        self.is_dragging = False

    def run(self) -> int:
        state = self.provider.read_state()
        if not state.enabled:
            print(f"PetEVA runtime stopped: {state.reason}")
            return 0

        self.raw_frames_by_row = self._load_raw_animation_rows()
        self._rebuild_scaled_frames()
        self._place_initial_random()
        self._tick_frame()
        self._tick_movement()
        self._poll_state()
        self._schedule_reminders()
        self.root.mainloop()
        return 0

    def _apply_window_transparency(self) -> None:
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        try:
            self.root.wm_attributes("-alpha", 1.0)
        except tk.TclError:
            pass

    def _bind_pointer_events(self, widget) -> None:
        self._bind_hover_events(widget)
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._drag)
        widget.bind("<ButtonRelease-1>", self._finish_drag)

    def _bind_hover_events(self, widget) -> None:
        widget.bind("<Enter>", self._show_toolbar)
        widget.bind("<Leave>", self._hide_toolbar_soon)

    def _build_hover_toolbar(self) -> tk.Frame:
        toolbar = tk.Frame(self.root, bg=TOOLBAR_BACKGROUND, borderwidth=0)
        for label, command in (
            ("-", self._shrink_pet),
            ("+", self._grow_pet),
            ("x", self._close_pet),
        ):
            button = tk.Button(
                toolbar,
                text=label,
                command=command,
                width=2,
                height=1,
                borderwidth=0,
                highlightthickness=0,
                bg=TOOLBAR_BACKGROUND,
                fg=TOOLBAR_FOREGROUND,
                activebackground="#343a43",
                activeforeground=TOOLBAR_FOREGROUND,
                takefocus=False,
            )
            button.pack(side=tk.LEFT, padx=1, pady=1)
            self._bind_hover_events(button)
        return toolbar

    def _build_reminder_label(self) -> tk.Label:
        return tk.Label(
            self.root,
            text="",
            bg=REMINDER_BACKGROUND,
            fg=REMINDER_FOREGROUND,
            padx=8,
            pady=5,
            borderwidth=0,
            justify=tk.CENTER,
            wraplength=160,
        )

    def _load_raw_animation_rows(self) -> dict[str, list[Image.Image]]:
        rows = {"idle": load_spritesheet_frames(self.spritesheet_path, row_name="idle")}
        codex_running_right = load_spritesheet_frames(self.spritesheet_path, row_name="running-right")
        codex_running_left = load_spritesheet_frames(self.spritesheet_path, row_name="running-left")
        codex_jumping = load_spritesheet_frames(self.spritesheet_path, row_name="jumping")
        rows["walking-right"] = self._load_motion_row_or_fallback("walking-right", codex_running_right)
        rows["walking-left"] = self._load_motion_row_or_fallback("walking-left", codex_running_left)
        rows["running-right"] = self._load_motion_row_or_fallback("running-right", rows["walking-right"])
        rows["running-left"] = self._load_motion_row_or_fallback("running-left", rows["walking-left"])
        rows["crawling-right"] = self._load_motion_row_or_fallback("crawling-right", rows["walking-right"])
        rows["crawling-left"] = self._load_motion_row_or_fallback("crawling-left", rows["walking-left"])
        rows["jumping"] = self._load_motion_row_or_fallback("jumping", codex_jumping)
        rows["jumping-right"] = self._load_motion_row_or_fallback("jumping-right", rows["jumping"])
        rows["jumping-left"] = self._load_motion_row_or_fallback("jumping-left", rows["jumping"])
        return rows

    def _load_motion_row_or_fallback(
        self,
        row_name: str,
        fallback: list[Image.Image],
    ) -> list[Image.Image]:
        frames_folder = self.spritesheet_path.parent / "source" / "frames"
        action_name, mirror = MOTION_PACK_ROWS.get(row_name, (row_name, False))
        motion_pack_folder = MOTION_PACK_FOLDER_TEMPLATE.format(unit_prefix=self.unit_prefix)
        motion_pack = frames_folder / motion_pack_folder / action_name
        frame_paths = [
            motion_pack / f"frame-{index:02d}.png"
            for index in range(1, MOTION_PACK_FRAME_COUNT + 1)
        ]
        if not all(frame_path.exists() for frame_path in frame_paths):
            return fallback

        frames = [Image.open(frame_path).convert("RGBA") for frame_path in frame_paths]
        if mirror:
            return [ImageOps.mirror(frame) for frame in frames]
        return frames

    def _rebuild_scaled_frames(self) -> None:
        self.tk_frames_by_row = {}
        for row_name, frames in self.raw_frames_by_row.items():
            self.tk_frames_by_row[row_name] = [
                ImageTk.PhotoImage(self._scale_frame(frame)) for frame in frames
            ]
        self._resize_canvas_to_current_frame()

    def _scale_frame(self, frame: Image.Image) -> Image.Image:
        if self.scale == 1:
            return frame
        width = max(1, int(frame.width * self.scale))
        height = max(1, int(frame.height * self.scale))
        return frame.resize((width, height), Image.Resampling.LANCZOS)

    def _resize_canvas_to_current_frame(self) -> None:
        frame = self._current_frames()[0]
        self.canvas.configure(width=frame.width(), height=frame.height())

    def _place_initial_random(self) -> None:
        self.root.update_idletasks()
        frame = self._current_frames()[0]
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        margin = self.motion_settings.screen_margin
        max_x = max(margin, screen_width - frame.width() - margin)
        max_y = max(margin, screen_height - frame.height() - margin)
        x = self.random_source.randint(margin, max_x)
        y = self.random_source.randint(margin, max_y)
        self.root.geometry(f"{frame.width()}x{frame.height()}+{x}+{y}")

    def _tick_frame(self) -> None:
        frames = self._current_frames()
        phase = self.frame_index % len(frames)
        self.canvas.delete("pet-sprite")
        self.canvas.create_image(
            0,
            0,
            anchor="nw",
            image=frames[phase],
            tags="pet-sprite",
        )
        self.rendered_frame_phase = phase
        if getattr(self, "waiting_for_segment_frame", False):
            self.waiting_for_segment_frame = False
        self.frame_index = (phase + 1) % len(frames)
        self.root.after(self.frame_ms, self._tick_frame)

    def _tick_movement(self) -> None:
        if not self.is_dragging and self.tk_frames_by_row:
            if self.movement_ticks_remaining <= 0:
                self.current_movement_step = choose_movement_step(
                    self.random_source,
                    self.motion_settings,
                )
                self.current_movement_step = self._redirect_step_away_from_edges(
                    self.current_movement_step,
                )
                self.current_row_name = self.current_movement_step.row_name
                self.frame_index = 0
                self.rendered_frame_phase = 0
                self.waiting_for_segment_frame = True
                self.movement_ticks_remaining = self._segment_tick_count(
                    self.current_movement_step,
                )

            if self.current_movement_step:
                if not getattr(self, "waiting_for_segment_frame", False):
                    self.movement_phase = self.rendered_frame_phase
                    dx, dy = movement_delta_for_phase(
                        self.current_movement_step,
                        self.movement_phase,
                        len(self._current_frames()),
                        self._jump_height_pixels(),
                    )
                    self._move_by(dx, dy)
                    self.movement_ticks_remaining -= 1
        self.root.after(self.move_ms, self._tick_movement)

    def _segment_tick_count(self, step: MovementStep) -> int:
        if step.movement_kind == "jump":
            return len(self._current_frames())
        return self.random_source.randint(
            self.motion_settings.min_segment_ticks,
            self.motion_settings.max_segment_ticks,
        )

    def _jump_height_pixels(self) -> int:
        frame = self._current_frames()[0]
        jump_height_scale = getattr(self.motion_settings, "jump_height_scale", 1.2)
        return max(1, round(frame.height() * jump_height_scale))

    def _redirect_step_away_from_edges(self, step: MovementStep) -> MovementStep:
        self.root.update_idletasks()
        frame = self._current_frames()[0]
        return redirect_step_away_from_edges(
            step=step,
            x=self.root.winfo_x(),
            y=self.root.winfo_y(),
            screen_width=self.root.winfo_screenwidth(),
            screen_height=self.root.winfo_screenheight(),
            window_width=frame.width(),
            window_height=frame.height(),
            margin=self.motion_settings.screen_margin,
        )

    def _move_by(self, dx: int, dy: int) -> None:
        if dx == 0 and dy == 0:
            return

        self.root.update_idletasks()
        frame = self._current_frames()[0]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        x, y = clamp_position(
            x=x,
            y=y,
            screen_width=self.root.winfo_screenwidth(),
            screen_height=self.root.winfo_screenheight(),
            window_width=frame.width(),
            window_height=frame.height(),
            margin=self.motion_settings.screen_margin,
        )
        self.root.geometry(f"{frame.width()}x{frame.height()}+{x}+{y}")

    def _poll_state(self) -> None:
        state = self.provider.read_state()
        if not state.enabled:
            print(f"PetEVA runtime stopped: {state.reason}")
            self.root.destroy()
            return
        self.root.after(self.poll_ms, self._poll_state)

    def _current_frames(self) -> list[ImageTk.PhotoImage]:
        return self.tk_frames_by_row.get(self.current_row_name) or self.tk_frames_by_row["idle"]

    def _show_toolbar(self, event=None) -> None:
        self.toolbar.place(x=4, y=4)
        self.toolbar.lift()

    def _schedule_reminders(self) -> None:
        for reminder in self.reminders:
            if getattr(reminder, "enabled", False):
                self.root.after(
                    getattr(reminder, "interval_ms"),
                    lambda active_reminder=reminder: self._show_reminder(active_reminder),
                )

    def _show_reminder(self, reminder) -> None:
        self.reminder_version += 1
        reminder_version = self.reminder_version
        self.reminder_label.configure(text=getattr(reminder, "message"))
        self.reminder_label.place(relx=0.5, y=34, anchor="n")
        self.reminder_label.lift()
        self.root.after(
            min(getattr(reminder, "display_ms"), 60_000),
            lambda: self._hide_reminder(reminder_version),
        )
        self.root.after(
            getattr(reminder, "interval_ms"),
            lambda: self._show_reminder(reminder),
        )

    def _hide_reminder(self, reminder_version: int) -> None:
        if reminder_version == self.reminder_version:
            self.reminder_label.place_forget()

    def _hide_toolbar_soon(self, event=None) -> None:
        self.root.after(400, self._hide_toolbar_if_pointer_left)

    def _hide_toolbar_if_pointer_left(self) -> None:
        pointer_x = self.root.winfo_pointerx()
        pointer_y = self.root.winfo_pointery()
        left = self.root.winfo_rootx()
        top = self.root.winfo_rooty()
        right = left + self.root.winfo_width()
        bottom = top + self.root.winfo_height()
        if not (left <= pointer_x <= right and top <= pointer_y <= bottom):
            self.toolbar.place_forget()

    def _shrink_pet(self) -> None:
        self._set_scale(max(0.45, self.scale - 0.1))

    def _grow_pet(self) -> None:
        self._set_scale(min(1.25, self.scale + 0.1))

    def _set_scale(self, scale: float) -> None:
        if abs(scale - self.scale) < 0.001:
            return

        self.scale = scale
        self._rebuild_scaled_frames()
        frame = self._current_frames()[0]
        x, y = clamp_position(
            x=self.root.winfo_x(),
            y=self.root.winfo_y(),
            screen_width=self.root.winfo_screenwidth(),
            screen_height=self.root.winfo_screenheight(),
            window_width=frame.width(),
            window_height=frame.height(),
            margin=self.motion_settings.screen_margin,
        )
        self.root.geometry(f"{frame.width()}x{frame.height()}+{x}+{y}")

    def _close_pet(self) -> None:
        self.root.destroy()

    def _start_drag(self, event) -> None:
        self.is_dragging = True
        self.drag_x = event.x
        self.drag_y = event.y

    def _drag(self, event) -> None:
        frame = self._current_frames()[0]
        x = self.root.winfo_pointerx() - self.drag_x
        y = self.root.winfo_pointery() - self.drag_y
        self.root.geometry(f"{frame.width()}x{frame.height()}+{x}+{y}")

    def _finish_drag(self, event=None) -> None:
        self.is_dragging = False

"""Build and launch the lightweight macOS runtime backend."""

from __future__ import annotations

from pathlib import Path
import subprocess

from .motion import MotionSettings


def run_macos_backend(
    project_root: Path,
    switch_file: Path,
    pet_folder: Path,
    unit_prefix: str,
    poll_ms: int,
    frame_ms: int,
    move_ms: int,
    scale: float,
    motion_settings: MotionSettings,
    reminders: tuple[object, ...],
) -> int:
    binary_path = build_macos_backend(project_root)
    frames_dir = pet_folder / "source" / "frames"
    command = [
        str(binary_path),
        "--switch-file",
        str(switch_file),
        "--frames-dir",
        str(frames_dir),
        "--unit-prefix",
        unit_prefix,
        "--poll-ms",
        str(poll_ms),
        "--frame-ms",
        str(frame_ms),
        "--move-ms",
        str(move_ms),
        "--scale",
        str(scale),
        "--step-pixels",
        str(motion_settings.step_pixels),
        "--run-step-pixels",
        str(motion_settings.run_step_pixels),
        "--jump-step-pixels",
        str(motion_settings.jump_step_pixels),
        "--crawl-step-pixels",
        str(motion_settings.crawl_step_pixels),
        "--jump-height-scale",
        str(motion_settings.jump_height_scale),
        "--direction-strategy",
        motion_settings.direction_strategy,
        "--stationary-chance",
        str(motion_settings.stationary_chance),
        "--horizontal-chance",
        str(motion_settings.horizontal_chance),
        "--vertical-chance",
        str(motion_settings.vertical_chance),
        "--diagonal-chance",
        str(motion_settings.diagonal_chance),
        "--walk-weight",
        str(motion_settings.walk_weight),
        "--run-weight",
        str(motion_settings.run_weight),
        "--crawl-weight",
        str(motion_settings.crawl_weight),
        "--jump-weight",
        str(motion_settings.jump_weight),
        "--vertical-jump-weight",
        str(motion_settings.vertical_jump_weight),
        "--vertical-walk-weight",
        str(motion_settings.vertical_walk_weight),
        "--screen-margin",
        str(motion_settings.screen_margin),
        "--min-segment-ticks",
        str(motion_settings.min_segment_ticks),
        "--max-segment-ticks",
        str(motion_settings.max_segment_ticks),
    ]
    command.extend(_reminder_args(reminders))
    return subprocess.run(command, check=False).returncode


def build_macos_backend(project_root: Path) -> Path:
    source_path = project_root / "runtime" / "peteva-runtime" / "macos" / "PetEVARuntime.swift"
    binary_path = project_root / "runtime" / "peteva-runtime" / "build" / "peteva-macos-runtime"
    binary_path.parent.mkdir(parents=True, exist_ok=True)

    if _needs_rebuild(source_path, binary_path):
        subprocess.run(
            ["swiftc", str(source_path), "-o", str(binary_path)],
            check=True,
        )

    return binary_path


def _needs_rebuild(source_path: Path, binary_path: Path) -> bool:
    if not binary_path.exists():
        return True
    return source_path.stat().st_mtime > binary_path.stat().st_mtime


def _reminder_args(reminders: tuple[object, ...]) -> list[str]:
    args: list[str] = []
    for reminder in reminders:
        reminder_id = getattr(reminder, "reminder_id")
        prefix = f"--{reminder_id}-reminder"
        args.extend([f"{prefix}-enabled", str(getattr(reminder, "enabled")).lower()])
        args.extend([f"{prefix}-interval-minutes", str(getattr(reminder, "interval_minutes"))])
        args.extend([f"{prefix}-message", str(getattr(reminder, "message"))])
        args.extend([f"{prefix}-display-seconds", str(getattr(reminder, "display_seconds"))])
    return args

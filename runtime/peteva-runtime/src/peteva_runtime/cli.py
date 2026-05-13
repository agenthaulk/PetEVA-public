"""Command-line entrypoint for the lightweight PetEVA runtime."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import sys

from .assets import default_pet_folder, default_switch_file, find_project_root, unit_asset_prefix
from .config import read_runtime_settings
from .lifecycle import LocalSwitchFileProvider, write_local_switch
from .macos_backend import run_macos_backend
from .motion import MotionSettings
from .window import PetWindow


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = find_project_root(Path(args.project_root or Path.cwd()))
    runtime_settings = read_runtime_settings(project_root)
    selected_unit_id = args.unit or runtime_settings.pet.active_unit_id
    window_settings = runtime_settings.window
    motion_settings = MotionSettings(
        step_pixels=args.step_pixels if args.step_pixels is not None else runtime_settings.motion.step_pixels,
        run_step_pixels=runtime_settings.motion.run_step_pixels,
        jump_step_pixels=runtime_settings.motion.jump_step_pixels,
        crawl_step_pixels=runtime_settings.motion.crawl_step_pixels,
        jump_height_scale=runtime_settings.motion.jump_height_scale,
        direction_strategy=runtime_settings.motion.direction_strategy,
        stationary_chance=runtime_settings.motion.stationary_chance,
        horizontal_chance=runtime_settings.motion.horizontal_chance,
        vertical_chance=runtime_settings.motion.vertical_chance,
        diagonal_chance=runtime_settings.motion.diagonal_chance,
        walk_weight=runtime_settings.motion.walk_weight,
        run_weight=runtime_settings.motion.run_weight,
        crawl_weight=runtime_settings.motion.crawl_weight,
        jump_weight=runtime_settings.motion.jump_weight,
        vertical_jump_weight=runtime_settings.motion.vertical_jump_weight,
        vertical_walk_weight=runtime_settings.motion.vertical_walk_weight,
        screen_margin=runtime_settings.motion.screen_margin,
        min_segment_ticks=runtime_settings.motion.min_segment_ticks,
        max_segment_ticks=runtime_settings.motion.max_segment_ticks,
    )
    poll_ms = args.poll_ms if args.poll_ms is not None else window_settings.poll_ms
    frame_ms = args.frame_ms if args.frame_ms is not None else window_settings.frame_ms
    move_ms = args.move_ms if args.move_ms is not None else window_settings.move_ms
    scale = args.scale if args.scale is not None else window_settings.scale
    switch_file = Path(args.switch_file) if args.switch_file else default_switch_file(project_root)

    if args.command == "enable":
        unit_asset_prefix(selected_unit_id)
        write_local_switch(switch_file, True, selected_unit_id)
        print(f"enabled {selected_unit_id}: {switch_file}")
        return 0

    if args.command == "disable":
        unit_asset_prefix(selected_unit_id)
        write_local_switch(switch_file, False, selected_unit_id)
        print(f"disabled {selected_unit_id}: {switch_file}")
        return 0

    provider = LocalSwitchFileProvider(switch_file, default_unit_id=selected_unit_id)
    state = provider.read_state()

    if args.command == "status":
        status = "enabled" if state.enabled else "disabled"
        print(f"{status} unit={state.unit_id} reason={state.reason}")
        return 0

    if not state.enabled:
        print(f"PetEVA runtime stopped: {state.reason}")
        return 0

    unit_prefix = unit_asset_prefix(state.unit_id)
    pet_folder = Path(args.pet_folder) if args.pet_folder else default_pet_folder(project_root, state.unit_id)
    if args.backend in {"auto", "macos"} and platform.system() == "Darwin":
        try:
            return run_macos_backend(
                project_root=project_root,
                switch_file=switch_file,
                pet_folder=pet_folder,
                unit_prefix=unit_prefix,
                poll_ms=poll_ms,
                frame_ms=frame_ms,
                move_ms=move_ms,
                scale=scale,
                motion_settings=motion_settings,
                reminders=runtime_settings.reminders,
            )
        except Exception as error:
            if args.backend == "macos":
                print(f"PetEVA macOS runtime error: {error}", file=sys.stderr)
                return 1
            print(f"PetEVA macOS runtime unavailable, falling back to Tk: {error}", file=sys.stderr)

    spritesheet_path = pet_folder / "spritesheet.webp"
    try:
        return PetWindow(
            provider=provider,
            spritesheet_path=spritesheet_path,
            poll_ms=poll_ms,
            frame_ms=frame_ms,
            move_ms=move_ms,
            scale=scale,
            motion_settings=motion_settings,
            reminders=runtime_settings.reminders,
            unit_prefix=unit_prefix,
        ).run()
    except Exception as error:
        print(f"PetEVA runtime error: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or control the PetEVA lightweight runtime.")
    parser.add_argument("command", choices=["run", "enable", "disable", "status"])
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--switch-file", default=None)
    parser.add_argument("--pet-folder", default=None)
    parser.add_argument("--unit", default=None)
    parser.add_argument("--poll-ms", type=int, default=None)
    parser.add_argument("--frame-ms", type=int, default=None)
    parser.add_argument("--move-ms", type=int, default=None)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--step-pixels", type=int, default=None)
    parser.add_argument("--backend", choices=["auto", "macos", "tk"], default="auto")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())

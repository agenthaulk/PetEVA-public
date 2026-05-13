"""Runtime config access for the lightweight PetEVA process."""

from __future__ import annotations

from pathlib import Path
import sys


def read_runtime_settings(project_root: Path):
    scripts_path = project_root / "scripts"
    if str(scripts_path) not in sys.path:
        sys.path.insert(0, str(scripts_path))

    from peteva_config import read_runtime_config

    return read_runtime_config(project_root / "config" / "default.yaml")

"""Convenience wrapper for the PetEVA lightweight runtime CLI."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = ROOT / "runtime" / "peteva-runtime" / "src"
sys.path.insert(0, str(RUNTIME_SRC))

from peteva_runtime.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

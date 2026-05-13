"""Install the built Unit-01 Codex pet into the local Codex pets folder."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the Unit-01 Codex pet locally.")
    parser.add_argument("--pet-folder", default="assets/codex-pets/eva-01")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME", "~/.codex"))
    parser.add_argument("--force", action="store_true", help="replace an existing eva-01 pet")
    args = parser.parse_args()

    project_root = Path.cwd()
    source = project_root / args.pet_folder
    target = Path(args.codex_home).expanduser() / "pets" / "eva-01"

    required_files = [source / "pet.json", source / "spritesheet.webp"]
    missing = [path for path in required_files if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing required file: {path}")
        return 1

    if target.exists():
        if not args.force:
            print(f"Target already exists: {target}")
            print("Re-run with --force to replace it.")
            return 1
        shutil.rmtree(target)

    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "pet.json", target / "pet.json")
    shutil.copy2(source / "spritesheet.webp", target / "spritesheet.webp")

    print(f"Installed Unit-01 Codex pet to {target}")
    print("In Codex Desktop, open Settings > Appearance > Pets and refresh custom pets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

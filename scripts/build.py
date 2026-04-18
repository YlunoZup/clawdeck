"""Build a one-file Windows executable with PyInstaller.

Usage:
    python scripts/build.py

Output:
    dist/clawdeck.exe
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "assets" / "icon.ico"


def run(cmd: list[str]) -> None:
    print("→", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode:
        sys.exit(r.returncode)


def main() -> None:
    # Ensure the runtime deps are installed
    run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"])

    dist = ROOT / "dist"
    build = ROOT / "build"
    for p in (dist, build):
        if p.exists():
            shutil.rmtree(p)

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "clawdeck",
        "--hidden-import", "clawdeck",
        "--collect-all", "flet",
        "--collect-all", "flet_desktop",
        "--collect-submodules", "pystray",
        "src/clawdeck/cli.py",
    ]
    if ICON.exists():
        args.extend(["--icon", str(ICON)])

    run(args)

    print("\n✓ Built:", dist / "clawdeck.exe")


if __name__ == "__main__":
    main()

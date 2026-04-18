"""Platform detection + OS-specific helpers."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def find_vboxmanage() -> Path | None:
    """Locate VBoxManage across supported platforms."""
    # Prefer PATH
    cmd = "VBoxManage.exe" if is_windows() else "VBoxManage"
    found = shutil.which(cmd)
    if found:
        return Path(found)

    # Common install locations
    candidates: list[Path] = []
    if is_windows():
        pfs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        for pf in pfs:
            if pf:
                candidates.append(Path(pf) / "Oracle" / "VirtualBox" / "VBoxManage.exe")
    elif is_macos():
        candidates += [
            Path("/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"),
            Path("/usr/local/bin/VBoxManage"),
        ]
    else:  # Linux
        candidates += [
            Path("/usr/bin/VBoxManage"),
            Path("/usr/local/bin/VBoxManage"),
        ]

    for c in candidates:
        if c.exists():
            return c

    return None


def executable_name() -> str:
    return "clawdeck.exe" if is_windows() else "clawdeck"

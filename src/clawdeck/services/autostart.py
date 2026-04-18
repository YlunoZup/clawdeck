"""Windows auto-start manager.

Uses HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run to register the app
for the current user (no admin required). macOS and Linux use LaunchAgents and
XDG autostart respectively — Phase 3.
"""

from __future__ import annotations

import logging
import sys

from ..utils.platform import is_windows

log = logging.getLogger(__name__)

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "ClawDeck"


def _import_winreg():
    if not is_windows():
        raise RuntimeError("autostart is only implemented on Windows")
    import winreg
    return winreg


def current_executable() -> str:
    """Return the command line used to start the app on login."""
    if getattr(sys, "frozen", False):
        # PyInstaller one-file exe
        return f'"{sys.executable}"'
    # Dev mode — fall back to the Python interpreter + module
    py = sys.executable
    pkg = "clawdeck"
    return f'"{py}" -m {pkg}'


def is_enabled() -> bool:
    if not is_windows():
        return False
    winreg = _import_winreg()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ
        ) as k:
            winreg.QueryValueEx(k, RUN_VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("autostart check failed: %s", exc)
        return False


def enable(command: str | None = None) -> None:
    if not is_windows():
        log.info("autostart.enable: no-op (non-Windows)")
        return
    winreg = _import_winreg()
    cmd = command or current_executable()
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
    ) as k:
        winreg.SetValueEx(k, RUN_VALUE_NAME, 0, winreg.REG_SZ, cmd)
    log.info("autostart enabled: %s", cmd)


def disable() -> None:
    if not is_windows():
        return
    winreg = _import_winreg()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as k:
            winreg.DeleteValue(k, RUN_VALUE_NAME)
        log.info("autostart disabled")
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("autostart disable failed: %s", exc)


def migrate_from_scheduled_task(task_name: str = "OpenClaw-AutoStart") -> bool:
    """Best-effort: remove the legacy scheduled task if present.

    Returns True if we removed it.
    """
    if not is_windows():
        return False
    import subprocess
    try:
        r = subprocess.run(
            ["schtasks.exe", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            log.info("removed legacy scheduled task %s", task_name)
            return True
    except (OSError, subprocess.SubprocessError) as exc:
        log.debug("schtasks delete failed: %s", exc)
    return False

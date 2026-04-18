"""Cross-platform autostart manager.

- Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
- macOS:   ~/Library/LaunchAgents/ai.openclaw.clawdeck.plist
- Linux:   ~/.config/autostart/clawdeck.desktop (XDG)

``current_executable()`` returns the right command line for the running
environment — the frozen .exe in production, or ``python -m clawdeck`` in
dev mode.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from ..utils.escaping import xml_escape
from ..utils.platform import is_linux, is_macos, is_windows

log = logging.getLogger(__name__)

APP_NAME = "ClawDeck"
APP_ID = "ai.openclaw.clawdeck"

# Windows
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = APP_NAME


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


def current_executable() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    py = sys.executable
    return f'"{py}" -m clawdeck'


def is_enabled() -> bool:
    if is_windows():
        return _win_is_enabled()
    if is_macos():
        return _macos_plist_path().exists()
    if is_linux():
        return _linux_desktop_path().exists()
    return False


def enable(command: str | None = None) -> None:
    cmd = command or current_executable()
    if is_windows():
        _win_enable(cmd)
    elif is_macos():
        _macos_enable(cmd)
    elif is_linux():
        _linux_enable(cmd)
    else:
        log.info("autostart.enable: unsupported platform")


def disable() -> None:
    if is_windows():
        _win_disable()
    elif is_macos():
        _macos_disable()
    elif is_linux():
        _linux_disable()


def migrate_from_scheduled_task(task_name: str = "OpenClaw-AutoStart") -> bool:
    """Best-effort cleanup of a legacy Windows scheduled task."""
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


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def _import_winreg():
    import winreg
    return winreg


def _win_is_enabled() -> bool:
    winreg = _import_winreg()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ,
        ) as k:
            winreg.QueryValueEx(k, RUN_VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("autostart check failed: %s", exc)
        return False


def _win_enable(cmd: str) -> None:
    winreg = _import_winreg()
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE,
    ) as k:
        winreg.SetValueEx(k, RUN_VALUE_NAME, 0, winreg.REG_SZ, cmd)
    log.info("autostart enabled: %s", cmd)


def _win_disable() -> None:
    winreg = _import_winreg()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE,
        ) as k:
            winreg.DeleteValue(k, RUN_VALUE_NAME)
        log.info("autostart disabled")
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("autostart disable failed: %s", exc)


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


def _macos_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"


def _macos_enable(cmd: str) -> None:
    path = _macos_plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # cmd is quote-wrapped like '"/path/to/exe"' — convert to argv
    argv = _parse_cmdline(cmd)
    args_xml = "\n".join(f"      <string>{xml_escape(a)}</string>" for a in argv)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>{APP_ID}</string>
    <key>ProgramArguments</key>
    <array>
{args_xml}
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><false/>
    <key>ProcessType</key><string>Interactive</string>
  </dict>
</plist>
"""
    path.write_text(plist, encoding="utf-8")
    log.info("autostart enabled: %s", path)


def _macos_disable() -> None:
    p = _macos_plist_path()
    try:
        p.unlink(missing_ok=True)
        log.info("autostart disabled: %s", p)
    except OSError as exc:
        log.warning("autostart disable failed: %s", exc)


# ---------------------------------------------------------------------------
# Linux (XDG)
# ---------------------------------------------------------------------------


def _linux_desktop_path() -> Path:
    base = (
        Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        / "autostart"
    )
    return base / "clawdeck.desktop"


def _linux_enable(cmd: str) -> None:
    path = _linux_desktop_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    exec_line = _unquote_cmdline(cmd)
    desktop = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "Comment=Personal desktop control panel for OpenClaw agents\n"
        f"Exec={exec_line}\n"
        "Icon=clawdeck\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    path.write_text(desktop, encoding="utf-8")
    log.info("autostart enabled: %s", path)


def _linux_disable() -> None:
    p = _linux_desktop_path()
    try:
        p.unlink(missing_ok=True)
        log.info("autostart disabled: %s", p)
    except OSError as exc:
        log.warning("autostart disable failed: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_cmdline(cmd: str) -> list[str]:
    """Shlex-ish parse of ``current_executable()`` output.

    We only ever produce strings like ``"/abs/path" -m clawdeck`` or
    ``"C:\\path\\clawdeck.exe"``, so a small-scale splitter is enough.
    """
    import shlex
    if os.name == "nt":
        # shlex.split(posix=False) keeps backslashes
        return shlex.split(cmd, posix=False)
    return shlex.split(cmd)


def _unquote_cmdline(cmd: str) -> str:
    """Remove wrapping quotes on individual tokens but keep them separated."""
    return " ".join(_parse_cmdline(cmd))



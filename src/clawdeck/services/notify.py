"""Cross-platform desktop notifications.

Tries the best available native API in order:
1. Windows  →  ``winrt.windows.ui.notifications`` (WinRT toast)
2. Windows  →  ``win10toast`` (fallback)
3. macOS    →  ``osascript`` via AppleScript
4. Linux    →  ``notify-send``
5. Anything →  log + no-op

Never raises to callers — failures are swallowed and logged.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

from ..utils.escaping import osa_escape, xml_escape
from ..utils.platform import is_linux, is_macos, is_windows

log = logging.getLogger(__name__)


@dataclass
class Notification:
    title: str
    body: str
    tag: str = "clawdeck"  # used for grouping / replacement


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def send(n: Notification) -> bool:
    """Best-effort send. Returns True on apparent success."""
    try:
        if is_windows():
            return _send_windows(n)
        if is_macos():
            return _send_macos(n)
        if is_linux():
            return _send_linux(n)
    except Exception as exc:  # never let a toast crash the app
        log.debug("notify failed: %s", exc)
    return False


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def _send_windows(n: Notification) -> bool:
    # Try the richer winrt API first; fall back to win10toast.
    try:
        return _send_windows_winrt(n)
    except Exception as exc:
        log.debug("winrt toast failed, trying win10toast: %s", exc)

    try:
        return _send_windows_legacy(n)
    except Exception as exc:
        log.debug("win10toast failed: %s", exc)

    return False


def _send_windows_winrt(n: Notification) -> bool:
    # Lazy import — winrt is optional
    try:
        from winrt.windows.data.xml.dom import XmlDocument  # type: ignore
        from winrt.windows.ui.notifications import (  # type: ignore
            ToastNotification,
            ToastNotificationManager,
        )
    except ImportError:
        return False

    xml = (
        "<toast><visual><binding template='ToastGeneric'>"
        f"<text>{xml_escape(n.title)}</text>"
        f"<text>{xml_escape(n.body)}</text>"
        "</binding></visual></toast>"
    )
    doc = XmlDocument()
    doc.load_xml(xml)
    toast = ToastNotification(doc)
    notifier = ToastNotificationManager.create_toast_notifier("ClawDeck")
    notifier.show(toast)
    return True


def _send_windows_legacy(n: Notification) -> bool:
    try:
        from win10toast import ToastNotifier  # type: ignore
    except ImportError:
        return False

    toaster = ToastNotifier()
    toaster.show_toast(n.title, n.body, threaded=True, duration=5)
    return True


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


def _send_macos(n: Notification) -> bool:
    script = (
        f'display notification "{osa_escape(n.body)}" '
        f'with title "{osa_escape(n.title)}"'
    )
    subprocess.run(
        ["osascript", "-e", script],
        check=False, capture_output=True, timeout=5,
    )
    return True


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------


def _send_linux(n: Notification) -> bool:
    if not shutil.which("notify-send"):
        return False
    subprocess.run(
        ["notify-send", "--app-name=ClawDeck", n.title, n.body],
        check=False, capture_output=True, timeout=5,
    )
    return True

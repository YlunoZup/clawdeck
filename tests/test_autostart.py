"""Autostart helpers — only checks non-Windows safe paths."""

from __future__ import annotations

from unittest.mock import patch

from clawdeck.services import autostart


def test_current_executable_is_non_empty():
    cmd = autostart.current_executable()
    assert cmd and len(cmd) > 3


def test_is_enabled_non_windows():
    with patch("clawdeck.services.autostart.is_windows", return_value=False):
        assert autostart.is_enabled() is False


def test_enable_non_windows_is_noop():
    with patch("clawdeck.services.autostart.is_windows", return_value=False):
        autostart.enable()   # should not raise

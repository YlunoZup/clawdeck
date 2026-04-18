"""Notification helpers — smoke tests that never actually pop a toast."""

from __future__ import annotations

from unittest.mock import patch

from clawdeck.services.notify import Notification, send


def test_send_never_raises():
    with (
        patch("clawdeck.services.notify.is_windows", return_value=False),
        patch("clawdeck.services.notify.is_macos", return_value=False),
        patch("clawdeck.services.notify.is_linux", return_value=False),
    ):
        assert send(Notification(title="Test", body="Body")) is False


def test_notification_defaults():
    n = Notification(title="t", body="b")
    assert n.tag == "clawdeck"

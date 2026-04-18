"""Tray icon generation smoke test."""

from __future__ import annotations

from clawdeck.models import OverallHealth
from clawdeck.ui.icons import build_icon


def test_build_icon_all_health_states():
    for h in OverallHealth:
        img = build_icon(h, size=64)
        assert img.size == (64, 64)
        assert img.mode == "RGBA"


def test_build_icon_custom_size():
    img = build_icon(OverallHealth.HEALTHY, size=128)
    assert img.size == (128, 128)

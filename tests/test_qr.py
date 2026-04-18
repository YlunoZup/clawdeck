"""QR PNG builder smoke test."""

from __future__ import annotations

from clawdeck.ui.components.qr import _build_png


def test_build_png_returns_png_bytes():
    data = _build_png("https://example.com", size=128)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 100


def test_build_png_respects_size():
    # We can't easily check pixel dimensions without Pillow, but we can
    # verify larger requests produce larger-ish payloads.
    small = _build_png("x", size=64)
    big = _build_png("x", size=512)
    assert len(big) > len(small)

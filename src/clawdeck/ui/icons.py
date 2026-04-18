"""Programmatic PIL-backed tray icon generation.

We draw a small lobster-claw-ish glyph in the status colour at runtime so the
app has no binary assets to ship. The exact shape is whimsical but recognisable
at 16×16 in the Windows taskbar.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from ..models import OverallHealth

COLOURS: dict[OverallHealth, tuple[int, int, int]] = {
    OverallHealth.HEALTHY:   (34, 197, 94),   # Tailwind emerald-500
    OverallHealth.DEGRADED:  (234, 179, 8),   # amber-500
    OverallHealth.UNHEALTHY: (239, 68, 68),   # red-500
    OverallHealth.OFFLINE:   (115, 115, 115), # neutral-500
}


def build_icon(health: OverallHealth, size: int = 64) -> Image.Image:
    """Return a square RGBA icon suitable for pystray."""
    bg = (0, 0, 0, 0)
    fg = (*COLOURS.get(health, COLOURS[OverallHealth.OFFLINE]), 255)

    img = Image.new("RGBA", (size, size), bg)
    d = ImageDraw.Draw(img)

    # Stylised claw: a thick ring with a pinched notch in the top-right
    stroke = max(4, size // 10)
    pad = stroke
    d.ellipse(
        (pad, pad, size - pad, size - pad),
        outline=fg,
        width=stroke,
    )

    # Notch — erase a wedge to suggest the claw opening
    notch_size = size // 3
    nx0 = size - pad - notch_size // 2
    ny0 = pad
    d.rectangle(
        (nx0, ny0, nx0 + notch_size, ny0 + notch_size),
        fill=bg,
    )

    # Inner pupil
    centre = size // 2
    inner = size // 6
    d.ellipse(
        (centre - inner, centre - inner, centre + inner, centre + inner),
        fill=fg,
    )
    return img

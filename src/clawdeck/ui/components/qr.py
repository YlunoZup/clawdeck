"""QR code widget — renders a URL as a QR image inside a Flet control.

Uses ``qrcode[pil]`` to build a PNG in-memory and displays it via
``ft.Image(src_base64=...)`` so the widget ships without any temp files.
"""

from __future__ import annotations

import base64
from io import BytesIO

import flet as ft
import qrcode
from PIL import Image


def _build_png(data: str, size: int = 256, dark: str = "black", light: str = "white") -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img: Image.Image = qr.make_image(fill_color=dark, back_color=light).convert("RGB")
    # Resize to the requested pixel dimensions for crisp display
    if img.size[0] != size:
        img = img.resize((size, size), Image.Resampling.NEAREST)
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def qr_image(data: str, size: int = 256) -> ft.Image:
    """Return a Flet Image showing the QR for ``data``."""
    png = _build_png(data, size=size)
    return ft.Image(
        src_base64=base64.b64encode(png).decode("ascii"),
        width=size,
        height=size,
        fit=ft.ImageFit.CONTAIN,
        border_radius=8,
    )

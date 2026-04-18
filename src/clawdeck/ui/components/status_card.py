"""Reusable status-card component."""

from __future__ import annotations

import flet as ft

from ...models import OverallHealth

COLOR_MAP: dict[str, str] = {
    "healthy":   "green",
    "degraded":  "amber",
    "unhealthy": "red",
    "offline":   "outline",
    "unknown":   "outline",
}


def status_card(title: str, value: str, health: OverallHealth | str) -> ft.Container:
    key = health.value if isinstance(health, OverallHealth) else str(health)
    color = COLOR_MAP.get(key, "outline")
    dot = ft.Container(
        width=12, height=12,
        border_radius=6,
        bgcolor=color,
    )
    return ft.Container(
        content=ft.Column(
            [
                ft.Row([dot, ft.Text(title, size=13, weight=ft.FontWeight.W_500)]),
                ft.Text(value, size=18, weight=ft.FontWeight.W_600),
            ],
            spacing=8,
        ),
        padding=16,
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.06, "primary"),
        expand=True,
    )

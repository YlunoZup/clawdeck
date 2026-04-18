"""Minimal sparkline using Flet's LineChart primitives."""

from __future__ import annotations

from collections.abc import Iterable

import flet as ft


def sparkline(
    values: Iterable[float],
    *,
    width: int = 180,
    height: int = 36,
    color: str = "primary",
    fill: bool = True,
) -> ft.LineChart:
    vals = list(values)
    if not vals:
        vals = [0.0]
    points = [ft.LineChartDataPoint(i, v) for i, v in enumerate(vals)]
    series = ft.LineChartData(
        data_points=points,
        stroke_width=2,
        color=color,
        curved=True,
        stroke_cap_round=True,
        below_line_bgcolor=ft.Colors.with_opacity(0.15, color) if fill else None,
    )
    return ft.LineChart(
        data_series=[series],
        width=width,
        height=height,
        border=None,
        tooltip_bgcolor=ft.Colors.with_opacity(0.9, "primary"),
        horizontal_grid_lines=ft.ChartGridLines(visible=False),
        vertical_grid_lines=ft.ChartGridLines(visible=False),
        left_axis=ft.ChartAxis(labels=[], labels_size=0),
        bottom_axis=ft.ChartAxis(labels=[], labels_size=0),
        min_y=0,
        max_y=max(vals) * 1.1 if max(vals) > 0 else 1.0,
    )

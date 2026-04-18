"""Usage / cost view."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

from ...core.usage import UsageAggregator, UsageSnapshot

if TYPE_CHECKING:
    from ...app import App


class UsageView(ft.Column):
    def __init__(self, app: App, loop: asyncio.AbstractEventLoop):
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self.app = app
        self.loop = loop

        self._aggregator = UsageAggregator(app.vm)

        self._totals_card = self._empty_totals()
        self._by_provider = ft.Column(spacing=6)
        self._by_day = ft.Column(spacing=6)

        self.controls = [
            ft.Row(
                [
                    ft.Text("Usage", size=22, weight=ft.FontWeight.W_700),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="Refresh",
                        on_click=lambda _: self._refresh(),
                    ),
                ],
            ),
            ft.Text(
                "Token and dollar totals from the last 7 days — pulled from "
                "`openclaw gateway usage-cost` inside the VM.",
                size=12, italic=True,
            ),
            self._totals_card,
            ft.Divider(),
            ft.Text("By provider", size=16, weight=ft.FontWeight.W_600),
            self._by_provider,
            ft.Divider(),
            ft.Text("By day", size=16, weight=ft.FontWeight.W_600),
            self._by_day,
        ]

        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------

    def on_attach(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._task = asyncio.run_coroutine_threadsafe(  # type: ignore[assignment]
            self._fetch_and_render(), self.loop,
        )

    async def _fetch_and_render(self) -> None:
        snap = await self._aggregator.snapshot(days=7)
        self._render(snap)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _empty_totals(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    _stat("Tokens in", "0"),
                    _stat("Tokens out", "0"),
                    _stat("USD spent", "$0.00"),
                ],
                spacing=24,
                wrap=True,
            ),
            padding=16,
            bgcolor=ft.Colors.with_opacity(0.06, "primary"),
            border_radius=12,
        )

    def _render(self, snap: UsageSnapshot) -> None:
        # Totals
        self._totals_card.content = ft.Row(
            [
                _stat("Tokens in", f"{snap.totals.input:,}"),
                _stat("Tokens out", f"{snap.totals.output:,}"),
                _stat("USD spent", f"${snap.totals.usd:,.2f}"),
            ],
            spacing=24,
            wrap=True,
        )

        # Per provider
        self._by_provider.controls = [
            _row(
                p.provider + (f" / {p.model}" if p.model else ""),
                [
                    _pill(f"in {p.input:,}"),
                    _pill(f"out {p.output:,}"),
                    _pill(f"${p.usd:,.2f}"),
                    _pill(f"{p.calls} calls"),
                ],
            )
            for p in snap.by_provider
        ] or [ft.Text("No provider data yet.", size=12, italic=True)]

        # Per day
        self._by_day.controls = [
            _row(
                d.day,
                [
                    _pill(f"in {d.input:,}"),
                    _pill(f"out {d.output:,}"),
                    _pill(f"${d.usd:,.2f}"),
                ],
            )
            for d in snap.by_day
        ] or [ft.Text("No daily data yet.", size=12, italic=True)]

        if self.page:
            self.update()


# ---------------------------------------------------------------------------
# Small widgets
# ---------------------------------------------------------------------------


def _stat(label: str, value: str) -> ft.Column:
    return ft.Column(
        [
            ft.Text(label, size=12, opacity=0.7),
            ft.Text(value, size=24, weight=ft.FontWeight.W_700),
        ],
        spacing=4,
    )


def _pill(text: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(text, size=11),
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        bgcolor=ft.Colors.with_opacity(0.1, "primary"),
        border_radius=999,
    )


def _row(title: str, pills: list[ft.Container]) -> ft.Row:
    return ft.Row(
        [
            ft.Text(title, size=13, weight=ft.FontWeight.W_500, width=200),
            ft.Row(pills, spacing=6, wrap=True),
        ],
    )

"""Tailscale view — tailnet status + exit-node picker."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

from ...core.tailscale import TailnetSnapshot, TailscaleController

if TYPE_CHECKING:
    from ...app import App


class TailscaleView(ft.Column):
    def __init__(self, app: App, loop: asyncio.AbstractEventLoop):
        super().__init__(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        self.app = app
        self.loop = loop
        self._ctl = TailscaleController()

        self._status_text = ft.Text("Checking Tailscale…", size=13)
        self._peers_col = ft.Column(spacing=8)
        self._exit_dd = ft.Dropdown(
            label="Exit node",
            width=340,
            options=[ft.dropdown.Option(key="", text="(none — direct)")],
            value="",
            on_change=self._on_exit_change,
        )

        self.controls = [
            ft.Row(
                [
                    ft.Text("Tailscale", size=22, weight=ft.FontWeight.W_700),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="Refresh",
                        on_click=lambda _: self._refresh(),
                    ),
                ],
            ),
            self._status_text,
            ft.Divider(),
            ft.Text("Exit node", size=16, weight=ft.FontWeight.W_600),
            ft.Text(
                "Route this machine's outbound traffic through a peer "
                "(useful for scraping with your Pi's home IP).",
                size=11, italic=True,
            ),
            self._exit_dd,
            ft.Divider(),
            ft.Text("Peers", size=16, weight=ft.FontWeight.W_600),
            self._peers_col,
        ]

        self._current_exit: str | None = None

    # ------------------------------------------------------------------

    def on_attach(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        asyncio.run_coroutine_threadsafe(self._load(), self.loop)

    async def _load(self) -> None:
        snap = await self._ctl.status()
        self._render(snap)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self, snap: TailnetSnapshot) -> None:
        if not snap.tailscale_installed:
            self._status_text.value = (
                "Tailscale CLI not found. Install Tailscale to enable this tab."
            )
            self._exit_dd.disabled = True
            self._peers_col.controls = []
            if self.page:
                self.update()
            return

        self._exit_dd.disabled = False
        self._current_exit = snap.exit_node_id
        self_desc = (
            f"{snap.current_node.hostname} "
            f"({', '.join(snap.current_node.addresses)})"
            if snap.current_node else "(unknown)"
        )
        self._status_text.value = (
            f"Backend: {snap.backend_state}  ·  Self: {self_desc}  ·  "
            f"Peers online: {len(snap.online_peers)}"
        )

        # Exit node dropdown
        options = [ft.dropdown.Option(key="", text="(none — direct)")]
        for p in snap.exit_node_candidates:
            online = "●" if p.online else "○"
            options.append(
                ft.dropdown.Option(
                    key=p.hostname,
                    text=f"{online} {p.hostname} · {p.os or '?'}",
                )
            )
        self._exit_dd.options = options
        self._exit_dd.value = snap.exit_node_id or ""

        # Peers list
        self._peers_col.controls = [self._peer_row(p) for p in snap.peers] or [
            ft.Text("No peers.", size=12, italic=True)
        ]

        if self.page:
            self.update()

    def _peer_row(self, p) -> ft.Container:
        dot = "green" if p.online else "outline"
        badges = []
        if p.is_exit_node_option:
            badges.append(_pill("exit-node capable"))
        if p.is_exit_node:
            badges.append(_pill("advertising exit"))
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(width=10, height=10, border_radius=5, bgcolor=dot),
                    ft.Column(
                        [
                            ft.Text(p.hostname, size=13, weight=ft.FontWeight.W_500),
                            ft.Text(
                                f"{p.os or '?'}  ·  {', '.join(p.addresses)}",
                                size=11, opacity=0.7, selectable=True,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Row(badges, spacing=4) if badges else ft.Container(),
                ],
                spacing=10,
            ),
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.06, "primary"),
        )

    # ------------------------------------------------------------------

    def _on_exit_change(self, e) -> None:
        val = self._exit_dd.value
        if val == (self._current_exit or ""):
            return

        async def go():
            ok = await self._ctl.set_exit_node(val or None)
            if self.page:
                self.page.open(
                    ft.SnackBar(
                        ft.Text("Exit node updated" if ok else "Failed to update exit node"),
                        duration=1500,
                    )
                )
            await self._load()

        asyncio.run_coroutine_threadsafe(go(), self.loop)


def _pill(text: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(text, size=10),
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
        bgcolor=ft.Colors.with_opacity(0.12, "primary"),
        border_radius=999,
    )

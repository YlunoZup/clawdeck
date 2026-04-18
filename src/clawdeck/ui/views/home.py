"""Home view — live status cards + quick actions + tunnel QR."""

from __future__ import annotations

import asyncio
import webbrowser
from typing import TYPE_CHECKING

import flet as ft

from ...models import (
    AppState,
    GatewayState,
    OverallHealth,
    TunnelState,
    VmState,
)
from ..components.qr import qr_image
from ..components.status_card import status_card

if TYPE_CHECKING:
    from ...app import App


class HomeView(ft.Column):
    def __init__(self, app: App, loop: asyncio.AbstractEventLoop):
        super().__init__(spacing=16, expand=True, scroll=ft.ScrollMode.AUTO)
        self.app = app
        self.loop = loop

        self._vm_card = status_card("VM", "unknown", OverallHealth.OFFLINE)
        self._gw_card = status_card("Gateway", "unknown", OverallHealth.OFFLINE)
        self._tn_card = status_card("Tunnel", "unknown", OverallHealth.OFFLINE)

        self._tunnel_url_text = ft.Text(
            "No tunnel detected yet.", size=12, selectable=True,
        )
        self._qr_holder = ft.Container(visible=False)
        self._qr_toggle = ft.TextButton(
            "Show QR for phone",
            icon=ft.Icons.QR_CODE_2,
            on_click=lambda _: self._toggle_qr(),
        )
        self._last_qr_url: str | None = None

        self.controls = [
            ft.Text("Overview", size=22, weight=ft.FontWeight.W_700),
            ft.Row(
                [self._vm_card, self._gw_card, self._tn_card],
                spacing=16,
            ),
            ft.Divider(height=8, color="transparent"),
            ft.Row(
                [
                    ft.Text("Tunnel URL", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(expand=True),
                    self._qr_toggle,
                    ft.IconButton(
                        icon=ft.Icons.CONTENT_COPY,
                        tooltip="Copy URL",
                        on_click=lambda _: self._copy_url(),
                    ),
                ],
            ),
            self._tunnel_url_text,
            self._qr_holder,
            ft.Divider(height=8, color="transparent"),
            ft.Text("Quick actions", size=14, weight=ft.FontWeight.W_500),
            ft.Row(
                [
                    ft.FilledButton(
                        "Start VM",
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=lambda _: self._spawn(self._start_vm()),
                    ),
                    ft.OutlinedButton(
                        "Stop VM",
                        icon=ft.Icons.STOP,
                        on_click=lambda _: self._spawn(self._stop_vm()),
                    ),
                    ft.OutlinedButton(
                        "Open Dashboard",
                        icon=ft.Icons.OPEN_IN_NEW,
                        on_click=lambda _: self._open_dashboard(),
                    ),
                    ft.TextButton(
                        "Reconnect Gateway",
                        icon=ft.Icons.REFRESH,
                        on_click=lambda _: self._spawn(self._reconnect()),
                    ),
                ],
                wrap=True,
                spacing=12,
            ),
        ]

    # ------------------------------------------------------------------
    # State → UI
    # ------------------------------------------------------------------

    def update_from_state(self, state: AppState) -> None:
        self._vm_card.content = status_card(
            "VM", state.vm.value, self._vm_health(state.vm)
        ).content
        self._gw_card.content = status_card(
            "Gateway", state.gateway.value, self._gw_health(state.gateway)
        ).content
        self._tn_card.content = status_card(
            "Tunnel", state.tunnel.value, self._tn_health(state.tunnel)
        ).content

        self._tunnel_url_text.value = state.tunnel_url or "No tunnel detected yet."

        # Refresh QR if URL changed and QR is currently visible
        if (
            self._qr_holder.visible
            and state.tunnel_url
            and state.tunnel_url != self._last_qr_url
        ):
            self._render_qr(state.tunnel_url)

        if self.page:
            self.update()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _vm_health(s: VmState) -> OverallHealth:
        return (
            OverallHealth.HEALTHY if s == VmState.RUNNING
            else OverallHealth.OFFLINE if s == VmState.STOPPED
            else OverallHealth.DEGRADED
        )

    @staticmethod
    def _gw_health(s: GatewayState) -> OverallHealth:
        return (
            OverallHealth.HEALTHY if s == GatewayState.CONNECTED
            else OverallHealth.UNHEALTHY
            if s in {GatewayState.UNREACHABLE, GatewayState.ERROR}
            else OverallHealth.DEGRADED
        )

    @staticmethod
    def _tn_health(s: TunnelState) -> OverallHealth:
        return (
            OverallHealth.HEALTHY if s == TunnelState.UP
            else OverallHealth.UNHEALTHY if s == TunnelState.DOWN
            else OverallHealth.DEGRADED
        )

    def _spawn(self, coro) -> None:
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def _start_vm(self) -> None:
        await self.app.vm.ensure_running(headless=self.app.config.vm.headless)

    async def _stop_vm(self) -> None:
        await self.app.vm.stop(graceful=True)

    async def _reconnect(self) -> None:
        await self.app.gateway.close()
        try:
            await self.app.gateway.connect()
        except Exception:
            pass

    def _open_dashboard(self) -> None:
        url = self.app.get_dashboard_url() or self.app.config.gateway.http_url
        webbrowser.open(url)

    def _copy_url(self) -> None:
        url = self.app.get_dashboard_url()
        if not url:
            return
        if self.page:
            self.page.set_clipboard(url)
            self.page.open(
                ft.SnackBar(ft.Text("Tunnel URL copied"), duration=1500)
            )

    # ------------------------------------------------------------------
    # QR
    # ------------------------------------------------------------------

    def _toggle_qr(self) -> None:
        if self._qr_holder.visible:
            self._qr_holder.visible = False
            self._qr_toggle.text = "Show QR for phone"
            self._qr_toggle.icon = ft.Icons.QR_CODE_2
        else:
            url = self.app.get_dashboard_url()
            if not url:
                if self.page:
                    self.page.open(
                        ft.SnackBar(
                            ft.Text("Tunnel URL not yet detected"), duration=1500,
                        )
                    )
                return
            self._render_qr(url)
            self._qr_holder.visible = True
            self._qr_toggle.text = "Hide QR"
            self._qr_toggle.icon = ft.Icons.CLOSE
        if self.page:
            self.update()

    def _render_qr(self, url: str) -> None:
        self._last_qr_url = url
        self._qr_holder.content = ft.Column(
            [
                ft.Container(
                    content=qr_image(url, size=240),
                    padding=8,
                    bgcolor="white",
                    border_radius=12,
                ),
                ft.Text(url, size=11, selectable=True),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

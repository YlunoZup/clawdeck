"""Absolute-import entry point for ``clawdeck`` and ``python -m clawdeck``.

Runs Flet on the main thread, pystray on its own, and an asyncio loop on a
third. State from the monitor is pushed to both UI subsystems plus the
origin-sync and notification services.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading

import flet as ft

from clawdeck.app import App
from clawdeck.models import AppState, GatewayState, OverallHealth, TunnelState
from clawdeck.services.notify import Notification
from clawdeck.services.notify import send as send_toast
from clawdeck.ui.tray import TrayController
from clawdeck.ui.window import MainWindow

log = logging.getLogger(__name__)


class BackgroundLoop:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="clawdeck.asyncio", daemon=True,
        )

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=3)

    def submit(self, coro) -> None:
        asyncio.run_coroutine_threadsafe(coro, self.loop)


class StateHub:
    """Fan-out for ``AppState`` changes — tray, window, notifier, origin sync.

    Also tracks the previous health + tunnel URL so it can emit toasts only
    on transitions (no spam).
    """

    def __init__(
        self,
        app: App,
        tray: TrayController,
        window_holder: dict[str, MainWindow],
    ):
        self.app = app
        self.tray = tray
        self.window_holder = window_holder

        self._prev_health: OverallHealth | None = None
        self._prev_tunnel_url: str | None = None
        self._prev_gateway: GatewayState | None = None
        self._prev_tunnel_state: TunnelState | None = None

    async def handle(self, state: AppState) -> None:
        # UI fan-out
        try:
            self.tray.on_state(state)
        except Exception:
            log.exception("tray.on_state failed")
        w = self.window_holder.get("window")
        if w is not None:
            try:
                w.on_state(state)
            except Exception:
                log.exception("window.on_state failed")

        # Notifications on transitions
        self._maybe_toast_transitions(state)

        # Auto-sync tunnel URL → gateway allowedOrigins
        try:
            await self.app.origin_sync.maybe_sync(state)
        except Exception:
            log.exception("origin_sync failed")

    def _maybe_toast_transitions(self, state: AppState) -> None:
        health = state.overall()

        # Tunnel URL rotation
        if (
            state.tunnel_url
            and self._prev_tunnel_url
            and state.tunnel_url != self._prev_tunnel_url
        ):
            send_toast(
                Notification(
                    title="Tunnel URL rotated",
                    body=state.tunnel_url,
                )
            )
        self._prev_tunnel_url = state.tunnel_url

        # Gateway came online
        if (
            self._prev_gateway is not None
            and state.gateway == GatewayState.CONNECTED
            and self._prev_gateway != GatewayState.CONNECTED
        ):
            send_toast(
                Notification(
                    title="Gateway online",
                    body="OpenClaw gateway is reachable. Ready to chat.",
                )
            )
        self._prev_gateway = state.gateway

        # Health regressions (red transitions)
        if (
            health == OverallHealth.UNHEALTHY
            and self._prev_health != OverallHealth.UNHEALTHY
        ):
            send_toast(
                Notification(
                    title="ClawDeck stack unhealthy",
                    body=(
                        f"Gateway {state.gateway.value}, "
                        f"VM {state.vm.value}, "
                        f"Tunnel {state.tunnel.value}"
                    ),
                )
            )

        # Tunnel went from up to down
        if (
            self._prev_tunnel_state == TunnelState.UP
            and state.tunnel == TunnelState.DOWN
        ):
            send_toast(
                Notification(
                    title="Tunnel down",
                    body="Public tunnel stopped responding. Restart it from the tray.",
                )
            )
        self._prev_tunnel_state = state.tunnel

        self._prev_health = health


def main() -> int:
    app = App.assemble()

    bg = BackgroundLoop()
    bg.start()

    window_holder: dict[str, MainWindow] = {}

    def open_main_window() -> None:
        w = window_holder.get("window")
        if w is None or w.page is None:
            return
        page = w.page
        try:
            page.window.visible = True
            page.window.to_front()
            page.update()
        except Exception:
            log.debug("open main window failed", exc_info=True)

    def on_tray_quit() -> None:
        bg.submit(app.monitor.stop())
        bg.submit(app.stop_stack(stop_vm=False))

    tray = TrayController(
        app=app,
        loop=bg.loop,
        on_open_main_window=open_main_window,
        on_quit=on_tray_quit,
    )
    tray.start()

    hub = StateHub(app=app, tray=tray, window_holder=window_holder)
    app.monitor.subscribe(hub.handle)

    bg.submit(app.start_stack())
    bg.submit(app.monitor.start())

    def flet_target(page: ft.Page) -> None:
        win = MainWindow(app=app, loop=bg.loop)
        window_holder["window"] = win
        win.build(page)

        def on_window_event(e):
            if getattr(e, "data", None) == "close":
                try:
                    page.window.visible = False
                    page.update()
                except Exception:
                    log.debug("hide-to-tray failed", exc_info=True)

        page.window.prevent_close = True
        page.window.on_event = on_window_event

    try:
        runner = getattr(ft, "run", None) or getattr(ft, "app", None)
        if runner is None:
            raise RuntimeError("flet has no `run` or `app` function")
        runner(target=flet_target)
    finally:
        tray.stop()
        bg.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())

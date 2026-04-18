"""System tray integration using pystray.

pystray wants to run on its own thread (it owns the Windows message pump). We
marshal menu-click actions back into the asyncio loop with
``asyncio.run_coroutine_threadsafe``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import webbrowser
from collections.abc import Callable
from typing import TYPE_CHECKING

import pystray

from ..models import AppState, OverallHealth
from .icons import build_icon

if TYPE_CHECKING:
    from ..app import App

log = logging.getLogger(__name__)


class TrayController:
    """Runs a pystray icon on a background thread.

    Responsibilities:
      - show an icon coloured by current health
      - provide a menu for start/stop/open/quit
      - re-render on state changes via ``on_state(state)``
    """

    def __init__(
        self,
        app: App,
        loop: asyncio.AbstractEventLoop,
        on_open_main_window: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ):
        self.app = app
        self.loop = loop
        self._on_open_main = on_open_main_window
        self._on_quit = on_quit
        self._thread: threading.Thread | None = None
        self._icon: pystray.Icon | None = None
        self._current_health: OverallHealth = OverallHealth.OFFLINE

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        icon = pystray.Icon(
            name="clawdeck",
            icon=build_icon(self._current_health),
            title="ClawDeck — starting…",
            menu=self._build_menu(),
        )
        self._icon = icon
        self._thread = threading.Thread(
            target=icon.run, name="clawdeck.tray", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
        if self._thread:
            self._thread.join(timeout=3)

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def on_state(self, state: AppState) -> None:
        health = state.overall()
        if health == self._current_health and self._icon is not None:
            # Only title changes
            self._icon.title = self._title_for(state)
            return

        self._current_health = health
        if self._icon is not None:
            self._icon.icon = build_icon(health)
            self._icon.title = self._title_for(state)
            self._icon.update_menu()

    @staticmethod
    def _title_for(state: AppState) -> str:
        parts = [
            f"VM: {state.vm.value}",
            f"Gateway: {state.gateway.value}",
            f"Tunnel: {state.tunnel.value}",
        ]
        return "ClawDeck — " + " · ".join(parts)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> pystray.Menu:
        def coro(fn):
            def wrapper(icon, item=None):
                try:
                    asyncio.run_coroutine_threadsafe(fn(), self.loop)
                except Exception:
                    log.exception("menu action failed")
            return wrapper

        def plain(fn):
            def wrapper(icon, item=None):
                try:
                    fn()
                except Exception:
                    log.exception("menu action failed")
            return wrapper

        def quit_(icon, item=None):
            try:
                if self._on_quit:
                    self._on_quit()
            finally:
                icon.stop()

        return pystray.Menu(
            pystray.MenuItem(
                "Open ClawDeck",
                plain(self._open_main_window),
                default=True,
            ),
            pystray.MenuItem(
                "Open Dashboard", plain(self._open_dashboard)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Start VM", coro(self._start_vm)
            ),
            pystray.MenuItem(
                "Stop VM", coro(self._stop_vm)
            ),
            pystray.MenuItem(
                "Restart gateway", coro(self._restart_gateway)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Copy tunnel URL", plain(self._copy_tunnel_url)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", quit_),
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_main_window(self) -> None:
        if self._on_open_main:
            self._on_open_main()

    def _open_dashboard(self) -> None:
        url = self.app.get_dashboard_url()
        if not url:
            url = self.app.config.gateway.http_url
        webbrowser.open(url)

    async def _start_vm(self) -> None:
        await self.app.vm.ensure_running(headless=self.app.config.vm.headless)

    async def _stop_vm(self) -> None:
        await self.app.vm.stop(graceful=True)

    async def _restart_gateway(self) -> None:
        await self.app.gateway.close()
        try:
            await self.app.gateway.connect()
        except Exception as exc:
            log.warning("restart gateway reconnect failed: %s", exc)

    def _copy_tunnel_url(self) -> None:
        url = self.app.get_dashboard_url()
        if not url:
            return
        try:
            import pyperclip  # type: ignore
            pyperclip.copy(url)
        except ImportError:
            # Fall back to Windows clip pipe
            try:
                import subprocess
                subprocess.run(
                    ["clip"], input=url.encode(), check=False
                )
            except OSError:
                pass

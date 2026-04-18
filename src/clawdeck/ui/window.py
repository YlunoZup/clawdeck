"""Main Flet window composition."""

from __future__ import annotations

import asyncio
import logging
import webbrowser
from typing import TYPE_CHECKING

import flet as ft

from ..models import AppState
from ..services.updater import Release, UpdateChecker
from .views.chat import ChatView
from .views.cron import CronView
from .views.home import HomeView
from .views.logs import LogsView
from .views.settings import SettingsView
from .views.tailscale import TailscaleView
from .views.usage import UsageView
from .wizard import FirstRunWizard

if TYPE_CHECKING:
    from ..app import App

log = logging.getLogger(__name__)


class MainWindow:
    def __init__(self, app: App, loop: asyncio.AbstractEventLoop):
        self.app = app
        self.loop = loop
        self.page: ft.Page | None = None

        self._home: HomeView | None = None
        self._chat: ChatView | None = None
        self._logs: LogsView | None = None
        self._usage: UsageView | None = None
        self._cron: CronView | None = None
        self._tailscale: TailscaleView | None = None
        self._settings: SettingsView | None = None

        self._update_banner: ft.Container | None = None
        self._profile_dd: ft.Dropdown | None = None

    def build(self, page: ft.Page) -> None:
        self.page = page
        page.title = "ClawDeck"
        page.window.width = 1100
        page.window.height = 720
        page.window.min_width = 780
        page.window.min_height = 560
        page.padding = 16
        page.theme_mode = self._theme_mode(self.app.config.app.theme)

        self._home = HomeView(self.app, self.loop)
        self._chat = ChatView(self.app, self.loop)
        self._logs = LogsView(self.loop)
        self._usage = UsageView(self.app, self.loop)
        self._cron = CronView(self.app, self.loop)
        self._tailscale = TailscaleView(self.app, self.loop)
        self._settings = SettingsView(self.app, self.loop)

        def attach(view):
            fn = getattr(view, "on_attach", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    log.debug("on_attach failed", exc_info=True)
            return view

        # Top bar: profile switcher + update banner
        self._profile_dd = ft.Dropdown(
            label="Profile",
            width=220,
            options=[
                ft.dropdown.Option(key=p.id, text=p.label)
                for p in self.app.profiles.all()
            ],
            value=self.app.profiles.active.id,
            on_change=self._on_profile_change,
        )

        self._update_banner = ft.Container(visible=False)

        top_bar = ft.Row(
            [
                ft.Text("ClawDeck", size=18, weight=ft.FontWeight.W_700),
                ft.Container(expand=True),
                self._profile_dd,
            ],
            spacing=12,
        )

        tabs = ft.Tabs(
            selected_index=0,
            expand=True,
            on_change=self._on_tab_change,
            tabs=[
                ft.Tab(text="Home", icon=ft.Icons.HOME,
                       content=ft.Container(content=self._home, padding=12)),
                ft.Tab(text="Chat", icon=ft.Icons.CHAT,
                       content=ft.Container(content=attach(self._chat), padding=12)),
                ft.Tab(text="Logs", icon=ft.Icons.ARTICLE,
                       content=ft.Container(content=self._logs, padding=12)),
                ft.Tab(text="Usage", icon=ft.Icons.BAR_CHART,
                       content=ft.Container(content=self._usage, padding=12)),
                ft.Tab(text="Cron", icon=ft.Icons.SCHEDULE,
                       content=ft.Container(content=self._cron, padding=12)),
                ft.Tab(text="Tailscale", icon=ft.Icons.HUB,
                       content=ft.Container(content=self._tailscale, padding=12)),
                ft.Tab(text="Settings", icon=ft.Icons.SETTINGS,
                       content=ft.Container(content=self._settings, padding=12)),
            ],
        )

        page.add(
            ft.Column(
                [top_bar, self._update_banner, tabs],
                expand=True,
                spacing=8,
            )
        )

        self._logs.start_tailing()

        # First-run wizard
        wizard = FirstRunWizard(self.app, self.loop)
        if wizard.should_show():
            wizard.open(page)

        # Non-blocking update check
        if self.app.config.app.check_updates:
            asyncio.run_coroutine_threadsafe(self._check_for_update(), self.loop)

    # ------------------------------------------------------------------
    # Tabs / navigation
    # ------------------------------------------------------------------

    def _on_tab_change(self, e) -> None:
        idx = e.control.selected_index
        # Lazy refresh heavy tabs
        if idx == 3 and self._usage:
            self._usage.on_attach()
        elif idx == 4 and self._cron:
            self._cron.on_attach()
        elif idx == 5 and self._tailscale:
            self._tailscale.on_attach()
        elif idx == 1 and self._chat:
            self._chat.on_attach()

    def _on_profile_change(self, e) -> None:
        if self._profile_dd is None or self._profile_dd.value is None:
            return
        try:
            self.app.profiles.switch(self._profile_dd.value)
        except KeyError:
            return
        # Phase 3: we only persist the selection and inform the user.
        # Phase 4 hot-swaps the monitor + gateway without relaunching.
        if self.page:
            self.page.open(
                ft.SnackBar(
                    ft.Text(
                        "Profile switched — restart ClawDeck for it to take effect.",
                    ),
                    duration=3000,
                )
            )

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def on_state(self, state: AppState) -> None:
        if self._home is not None:
            try:
                self._home.update_from_state(state)
            except Exception:
                log.debug("home update failed", exc_info=True)

    # ------------------------------------------------------------------
    # Update checker
    # ------------------------------------------------------------------

    async def _check_for_update(self) -> None:
        try:
            checker = UpdateChecker()
            release = await checker.has_update()
            if release is not None:
                self._show_update_banner(release)
        except Exception:
            log.debug("update check failed", exc_info=True)

    def _show_update_banner(self, release: Release) -> None:
        if self._update_banner is None:
            return
        body = ft.Row(
            [
                ft.Icon(ft.Icons.SYSTEM_UPDATE, color="primary"),
                ft.Text(
                    f"ClawDeck {release.tag} is available.",
                    size=13, weight=ft.FontWeight.W_500,
                ),
                ft.Container(expand=True),
                ft.TextButton(
                    "Open release",
                    icon=ft.Icons.OPEN_IN_NEW,
                    on_click=lambda _: webbrowser.open(release.url),
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    tooltip="Dismiss",
                    on_click=lambda _: self._hide_update_banner(),
                ),
            ],
            spacing=8,
        )
        self._update_banner.content = body
        self._update_banner.padding = 10
        self._update_banner.border_radius = 8
        self._update_banner.bgcolor = ft.Colors.with_opacity(0.12, "primary")
        self._update_banner.visible = True
        if self.page:
            self.page.update()

    def _hide_update_banner(self) -> None:
        if self._update_banner is not None:
            self._update_banner.visible = False
            if self.page:
                self.page.update()

    # ------------------------------------------------------------------

    @staticmethod
    def _theme_mode(value: str) -> ft.ThemeMode:
        v = (value or "auto").lower()
        if v == "light":
            return ft.ThemeMode.LIGHT
        if v == "dark":
            return ft.ThemeMode.DARK
        return ft.ThemeMode.SYSTEM

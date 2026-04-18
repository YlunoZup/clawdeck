"""Main Flet window composition."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import flet as ft

from ..models import AppState
from .views.chat import ChatView
from .views.cron import CronView
from .views.home import HomeView
from .views.logs import LogsView
from .views.settings import SettingsView
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
        self._settings: SettingsView | None = None

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
        self._settings = SettingsView(self.app, self.loop)

        def attach(view):
            fn = getattr(view, "on_attach", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    log.debug("on_attach failed", exc_info=True)
            return view

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
                ft.Tab(text="Settings", icon=ft.Icons.SETTINGS,
                       content=ft.Container(content=self._settings, padding=12)),
            ],
        )
        page.add(tabs)

        self._logs.start_tailing()

        # First-run wizard
        wizard = FirstRunWizard(self.app, self.loop)
        if wizard.should_show():
            wizard.open(page)

    # ------------------------------------------------------------------

    def _on_tab_change(self, e) -> None:
        """Lazy-refresh tabs that are expensive to keep live."""
        idx = e.control.selected_index
        if idx == 3 and self._usage:
            self._usage.on_attach()
        elif idx == 4 and self._cron:
            self._cron.on_attach()
        elif idx == 1 and self._chat:
            self._chat.on_attach()

    # ------------------------------------------------------------------

    def on_state(self, state: AppState) -> None:
        if self._home is not None:
            try:
                self._home.update_from_state(state)
            except Exception:
                log.debug("home update failed", exc_info=True)

    @staticmethod
    def _theme_mode(value: str) -> ft.ThemeMode:
        v = (value or "auto").lower()
        if v == "light":
            return ft.ThemeMode.LIGHT
        if v == "dark":
            return ft.ThemeMode.DARK
        return ft.ThemeMode.SYSTEM

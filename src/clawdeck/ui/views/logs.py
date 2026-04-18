"""Logs view with filters + search."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import flet as ft

from ...utils.paths import log_dir

POLL_SECONDS = 1.5
LEVELS: tuple[str, ...] = ("ALL", "DEBUG", "INFO", "WARNING", "ERROR")


class LogsView(ft.Column):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__(expand=True, spacing=8)
        self.loop = loop
        self._path: Path = log_dir() / "clawdeck.log"

        self._raw_lines: list[str] = []
        self._filter_level: str = "ALL"
        self._search: str = ""
        self._auto_follow = True

        self._text = ft.TextField(
            value="",
            multiline=True,
            read_only=True,
            min_lines=22,
            max_lines=30,
            text_size=12,
            expand=True,
        )

        self._level_dd = ft.Dropdown(
            label="Level",
            width=150,
            value="ALL",
            options=[ft.dropdown.Option(v) for v in LEVELS],
            on_change=self._on_level_change,
        )
        self._search_box = ft.TextField(
            label="Search",
            hint_text="filter text",
            expand=True,
            on_change=self._on_search_change,
            suffix_icon=ft.Icons.SEARCH,
        )
        self._auto_sw = ft.Switch(
            label="Auto-follow", value=True, on_change=self._on_auto_change,
        )

        self.controls = [
            ft.Row(
                [
                    ft.Text("Logs", size=22, weight=ft.FontWeight.W_700),
                    ft.Container(expand=True),
                    ft.TextButton(
                        "Copy visible",
                        icon=ft.Icons.CONTENT_COPY,
                        on_click=lambda _: self._copy_visible(),
                    ),
                    ft.TextButton(
                        "Open folder",
                        icon=ft.Icons.FOLDER,
                        on_click=lambda _: self._open_folder(),
                    ),
                ],
            ),
            ft.Text(str(self._path), size=11, italic=True),
            ft.Row([self._level_dd, self._search_box, self._auto_sw]),
            self._text,
        ]

        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------

    def start_tailing(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.run_coroutine_threadsafe(  # type: ignore[assignment]
            self._tail_loop(), self.loop
        )

    def stop_tailing(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def _on_level_change(self, e):
        self._filter_level = (self._level_dd.value or "ALL").upper()
        self._render()

    def _on_search_change(self, e):
        self._search = (self._search_box.value or "").lower()
        self._render()

    def _on_auto_change(self, e):
        self._auto_follow = bool(self._auto_sw.value)

    def _line_matches(self, line: str) -> bool:
        if self._filter_level != "ALL" and f"[{self._filter_level}]" not in line:
            return False
        return not (self._search and self._search not in line.lower())

    def _render(self) -> None:
        lines = [ln for ln in self._raw_lines if self._line_matches(ln)]
        # Keep textbox lively by capping
        self._text.value = "\n".join(lines[-200:])
        if self.page:
            self.update()

    # ------------------------------------------------------------------
    # Tail loop
    # ------------------------------------------------------------------

    async def _tail_loop(self) -> None:
        last_size = 0
        while True:
            try:
                if self._path.exists():
                    size = self._path.stat().st_size
                    if size != last_size:
                        last_size = size
                        try:
                            text = self._path.read_text(
                                encoding="utf-8", errors="replace",
                            )
                        except OSError:
                            text = ""
                        self._raw_lines = text.splitlines()[-2000:]
                        self._render()
            except Exception:
                pass
            await asyncio.sleep(POLL_SECONDS)

    # ------------------------------------------------------------------

    def _copy_visible(self) -> None:
        if self.page and self._text.value:
            self.page.set_clipboard(self._text.value)
            self.page.open(
                ft.SnackBar(ft.Text("Copied log to clipboard"), duration=1500)
            )

    def _open_folder(self) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(self._path.parent))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self._path.parent)])
            else:
                subprocess.Popen(["xdg-open", str(self._path.parent)])
        except Exception:
            pass

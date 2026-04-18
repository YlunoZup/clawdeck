"""Cron view — list, add, remove scheduled jobs."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

from ...core.cron import CronController, CronJob

if TYPE_CHECKING:
    from ...app import App


class CronView(ft.Column):
    def __init__(self, app: App, loop: asyncio.AbstractEventLoop):
        super().__init__(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        self.app = app
        self.loop = loop
        self._ctl = CronController(app.vm)

        self._list_col = ft.Column(spacing=8)
        self._sched = ft.TextField(
            label="Schedule (cron)", hint_text="0 9 * * *", expand=True,
        )
        self._cmd = ft.TextField(
            label="Command", hint_text="send morning summary", expand=True,
        )
        self._desc = ft.TextField(
            label="Description (optional)", expand=True,
        )

        self.controls = [
            ft.Row(
                [
                    ft.Text("Scheduled jobs", size=22, weight=ft.FontWeight.W_700),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="Refresh",
                        on_click=lambda _: self._refresh(),
                    ),
                ],
            ),
            ft.Text(
                "Wraps `openclaw cron` inside the VM. Jobs added here run on "
                "the OpenClaw schedule loop.",
                size=12, italic=True,
            ),
            self._list_col,
            ft.Divider(),
            ft.Text("New job", size=16, weight=ft.FontWeight.W_600),
            ft.Row([self._sched, self._cmd], spacing=8),
            self._desc,
            ft.Row(
                [
                    ft.FilledButton(
                        "Add",
                        icon=ft.Icons.ADD,
                        on_click=lambda _: self._add(),
                    ),
                ],
            ),
        ]

        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------

    def on_attach(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._task = asyncio.run_coroutine_threadsafe(  # type: ignore[assignment]
            self._load(), self.loop,
        )

    async def _load(self) -> None:
        jobs = await self._ctl.list()
        self._render(jobs)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self, jobs: list[CronJob]) -> None:
        if not jobs:
            self._list_col.controls = [
                ft.Text("No jobs yet.", size=12, italic=True)
            ]
        else:
            self._list_col.controls = [self._job_row(j) for j in jobs]
        if self.page:
            self.update()

    def _job_row(self, j: CronJob) -> ft.Container:
        dot_color = "green" if j.enabled else "outline"
        next_run = f"Next: {j.next_run}" if j.next_run else "Next: —"
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        width=10, height=10, border_radius=5, bgcolor=dot_color,
                    ),
                    ft.Column(
                        [
                            ft.Text(j.description or j.command, size=13),
                            ft.Text(
                                f"{j.schedule}  ·  {j.command}  ·  {next_run}",
                                size=11, opacity=0.7, selectable=True,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Switch(
                        value=j.enabled,
                        on_change=lambda e, jid=j.id: self._toggle(jid, e.control.value),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="Remove",
                        on_click=lambda _, jid=j.id: self._remove(jid),
                    ),
                ],
                spacing=10,
            ),
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.06, "primary"),
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add(self) -> None:
        sched = (self._sched.value or "").strip()
        cmd = (self._cmd.value or "").strip()
        desc = (self._desc.value or "").strip()
        if not sched or not cmd:
            if self.page:
                self.page.open(
                    ft.SnackBar(
                        ft.Text("Schedule and Command are required"),
                        duration=2000,
                    )
                )
            return

        async def go():
            ok = await self._ctl.add(schedule=sched, command=cmd, description=desc)
            if ok:
                self._sched.value = ""
                self._cmd.value = ""
                self._desc.value = ""
            await self._load()

        asyncio.run_coroutine_threadsafe(go(), self.loop)

    def _remove(self, job_id: str) -> None:
        async def go():
            await self._ctl.remove(job_id)
            await self._load()
        asyncio.run_coroutine_threadsafe(go(), self.loop)

    def _toggle(self, job_id: str, enabled: bool) -> None:
        async def go():
            await self._ctl.set_enabled(job_id, enabled)
            await self._load()
        asyncio.run_coroutine_threadsafe(go(), self.loop)

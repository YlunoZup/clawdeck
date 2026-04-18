"""Chat view with persistent history + session switcher."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

if TYPE_CHECKING:
    from ...app import App


class _Bubble(ft.Container):
    def __init__(self, role: str, text: str):
        align_end = role == "user"
        bg_key = "primary" if align_end else "secondary"
        super().__init__(
            content=ft.Text(text, selectable=True),
            padding=12,
            border_radius=14,
            bgcolor=ft.Colors.with_opacity(0.12, bg_key),
            margin=ft.margin.only(left=40 if align_end else 0, right=0 if align_end else 40),
            alignment=(
                ft.alignment.center_right if align_end else ft.alignment.center_left
            ),
        )


class ChatView(ft.Column):
    def __init__(self, app: App, loop: asyncio.AbstractEventLoop):
        super().__init__(expand=True, spacing=8)
        self.app = app
        self.loop = loop

        self._current_session_id: int | None = None

        self._list = ft.ListView(
            expand=True,
            spacing=8,
            auto_scroll=True,
            padding=ft.padding.symmetric(horizontal=8, vertical=8),
        )
        self._input = ft.TextField(
            hint_text="Message your agent…",
            expand=True,
            shift_enter=True,
            multiline=True,
            min_lines=1,
            max_lines=5,
            on_submit=lambda _: self._send(),
        )
        self._send_btn = ft.IconButton(
            icon=ft.Icons.SEND, tooltip="Send",
            on_click=lambda _: self._send(),
        )
        self._busy = ft.ProgressBar(visible=False)

        self._session_dd = ft.Dropdown(
            label="Session",
            width=260,
            on_change=self._on_switch_session,
        )

        new_btn = ft.IconButton(
            icon=ft.Icons.ADD,
            tooltip="New chat",
            on_click=lambda _: self._new_session(),
        )
        del_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            tooltip="Delete session",
            on_click=lambda _: self._delete_session(),
        )

        self.controls = [
            ft.Row(
                [
                    ft.Text("Chat", size=22, weight=ft.FontWeight.W_700),
                    ft.Container(expand=True),
                    self._session_dd,
                    new_btn,
                    del_btn,
                ],
            ),
            self._busy,
            ft.Container(
                content=self._list,
                expand=True,
                bgcolor=ft.Colors.with_opacity(0.04, "primary"),
                border_radius=12,
            ),
            ft.Row([self._input, self._send_btn], spacing=8),
        ]

    # ------------------------------------------------------------------
    # Attach/refresh
    # ------------------------------------------------------------------

    def on_attach(self) -> None:
        self._refresh_sessions()

    def _refresh_sessions(self) -> None:
        sessions = self.app.history.list_sessions(limit=50)
        self._session_dd.options = [
            ft.dropdown.Option(
                key=str(s.id),
                text=f"{s.title[:40]} · {s.updated_at.strftime('%m-%d %H:%M')}",
            )
            for s in sessions
        ]
        if sessions:
            self._current_session_id = self._current_session_id or sessions[0].id
            self._session_dd.value = str(self._current_session_id)
            self._load_session(self._current_session_id)
        else:
            self._current_session_id = None
            self._session_dd.value = None
            self._list.controls = []
        if self.page:
            self.update()

    def _load_session(self, session_id: int) -> None:
        self._list.controls = [
            _Bubble(role=m.role, text=m.text)
            for m in self.app.history.list_messages(session_id)
        ]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_switch_session(self, e):
        val = self._session_dd.value
        if val is None:
            return
        self._current_session_id = int(val)
        self._load_session(self._current_session_id)
        if self.page:
            self.update()

    def _new_session(self) -> None:
        s = self.app.history.create_session(title="New chat")
        self._current_session_id = s.id
        self._refresh_sessions()

    def _delete_session(self) -> None:
        if self._current_session_id is None:
            return
        self.app.history.delete_session(self._current_session_id)
        self._current_session_id = None
        self._refresh_sessions()

    def _send(self) -> None:
        text = (self._input.value or "").strip()
        if not text:
            return
        self._input.value = ""
        self._list.controls.append(_Bubble("user", text))
        self._set_busy(True)
        if self.page:
            self.update()
        asyncio.run_coroutine_threadsafe(self._send_async(text), self.loop)

    def _set_busy(self, busy: bool) -> None:
        self._busy.visible = busy
        self._send_btn.disabled = busy
        self._input.disabled = busy
        if self.page:
            self.update()

    async def _send_async(self, text: str) -> None:
        try:
            reply, session_id = await self.app.send_chat(
                text, session_id=self._current_session_id,
            )
            self._current_session_id = session_id
            self._list.controls.append(_Bubble("agent", reply or "(empty reply)"))
        except Exception as exc:
            self._list.controls.append(
                _Bubble("system", f"⚠️ {type(exc).__name__}: {exc}")
            )
        finally:
            self._set_busy(False)
            # Refresh dropdown so new sessions show up
            self._refresh_sessions()

"""Settings view — config + secret management."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import flet as ft

from ... import config as config_mod
from ... import secrets
from ...services import autostart

if TYPE_CHECKING:
    from ...app import App


class SettingsView(ft.Column):
    def __init__(self, app: App, loop: asyncio.AbstractEventLoop):
        super().__init__(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        self.app = app
        self.loop = loop

        cfg = self.app.config

        self._theme = ft.Dropdown(
            label="Theme",
            options=[
                ft.dropdown.Option("auto"),
                ft.dropdown.Option("light"),
                ft.dropdown.Option("dark"),
            ],
            value=cfg.app.theme,
        )
        self._autostart = ft.Switch(
            label="Start ClawDeck with Windows",
            value=autostart.is_enabled(),
        )
        self._autostart_vm = ft.Switch(
            label="Auto-start VM when ClawDeck launches",
            value=cfg.vm.autostart_vm,
        )
        self._headless = ft.Switch(
            label="Run VM headless",
            value=cfg.vm.headless,
        )

        self._vm_name = ft.TextField(
            label="VM name", value=cfg.vm.name, expand=True,
        )
        self._guest_user = ft.TextField(
            label="Guest user", value=cfg.vm.guest_user, expand=True,
        )
        self._guest_password = ft.TextField(
            label="Guest password (only needed for log tailing)",
            value="",
            password=True,
            can_reveal_password=True,
            expand=True,
        )

        self._gw_host = ft.TextField(
            label="Gateway host", value=cfg.gateway.host, expand=True,
        )
        self._gw_port = ft.TextField(
            label="Gateway port",
            value=str(cfg.gateway.port),
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self._gw_password = ft.TextField(
            label="Gateway password",
            value="",
            password=True,
            can_reveal_password=True,
            expand=True,
            hint_text="leave empty to keep current",
        )

        self._tunnel_log = ft.TextField(
            label="Tunnel log path (on VM)",
            value=cfg.tunnel.log_path_on_vm,
            expand=True,
        )

        self._status = ft.Text("", size=12, italic=True)

        save_btn = ft.FilledButton(
            "Save", icon=ft.Icons.SAVE, on_click=lambda _: self._save()
        )

        self.controls = [
            ft.Text("Settings", size=22, weight=ft.FontWeight.W_700),
            ft.Text("General", size=16, weight=ft.FontWeight.W_600),
            self._theme,
            self._autostart,
            ft.Divider(),
            ft.Text("VM", size=16, weight=ft.FontWeight.W_600),
            self._vm_name,
            ft.Row([self._guest_user, self._guest_password]),
            self._autostart_vm,
            self._headless,
            ft.Divider(),
            ft.Text("Gateway", size=16, weight=ft.FontWeight.W_600),
            ft.Row([self._gw_host, self._gw_port]),
            self._gw_password,
            ft.Divider(),
            ft.Text("Tunnel", size=16, weight=ft.FontWeight.W_600),
            self._tunnel_log,
            ft.Divider(),
            ft.Row([save_btn, self._status]),
        ]

    # ------------------------------------------------------------------

    def _save(self) -> None:
        cfg = self.app.config
        cfg.app.theme = self._theme.value or "auto"
        cfg.vm.name = (self._vm_name.value or "").strip() or cfg.vm.name
        cfg.vm.guest_user = (self._guest_user.value or "").strip() or cfg.vm.guest_user
        cfg.vm.headless = bool(self._headless.value)
        cfg.vm.autostart_vm = bool(self._autostart_vm.value)
        cfg.gateway.host = (self._gw_host.value or cfg.gateway.host).strip()
        with contextlib.suppress(ValueError):
            cfg.gateway.port = int(self._gw_port.value or cfg.gateway.port)
        cfg.tunnel.log_path_on_vm = self._tunnel_log.value or cfg.tunnel.log_path_on_vm

        if self._gw_password.value:
            secrets.set_secret(secrets.GATEWAY_PASSWORD, self._gw_password.value)
            self.app.gateway.password = self._gw_password.value
        if self._guest_password.value:
            secrets.set_secret(secrets.VM_USER_PASSWORD, self._guest_password.value)
            self.app.vm.guest_password = self._guest_password.value

        config_mod.save(cfg)

        if self._autostart.value:
            autostart.enable()
        else:
            autostart.disable()

        self._status.value = "Saved ✓"
        if self.page:
            self.update()

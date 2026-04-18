"""First-run wizard — a modal dialog that walks the user through the essentials.

Steps:
 1. Detect VBoxManage + list VMs, let user pick one
 2. Prompt for guest user / password (optional)
 3. Prompt for gateway host/port/password
 4. Save config + mark ``app.first_run_complete = True``
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

from .. import config as config_mod
from .. import secrets
from ..utils.platform import find_vboxmanage

if TYPE_CHECKING:
    from ..app import App


class FirstRunWizard:
    def __init__(self, app: App, loop: asyncio.AbstractEventLoop):
        self.app = app
        self.loop = loop
        self._dialog: ft.AlertDialog | None = None
        self._page: ft.Page | None = None

    # ------------------------------------------------------------------

    def should_show(self) -> bool:
        return not self.app.config.app.first_run_complete

    def open(self, page: ft.Page) -> None:
        self._page = page

        vm_name = ft.TextField(
            label="VM name", value=self.app.config.vm.name, expand=True,
        )
        guest_user = ft.TextField(
            label="Guest user",
            value=self.app.config.vm.guest_user,
            expand=True,
        )
        guest_pass = ft.TextField(
            label="Guest password (optional)",
            password=True,
            can_reveal_password=True,
            expand=True,
        )
        gw_host = ft.TextField(
            label="Gateway host",
            value=self.app.config.gateway.host,
            expand=True,
        )
        gw_port = ft.TextField(
            label="Gateway port",
            value=str(self.app.config.gateway.port),
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        gw_pass = ft.TextField(
            label="Gateway password",
            password=True,
            can_reveal_password=True,
            expand=True,
        )

        vbx = find_vboxmanage()
        detected = (
            ft.Text(f"VBoxManage: {vbx}", size=11, color="green")
            if vbx else
            ft.Text(
                "VBoxManage not found. Install VirtualBox first.",
                size=11, color="red",
            )
        )

        def finish(_):
            # Save config
            cfg = self.app.config
            cfg.vm.name = (vm_name.value or cfg.vm.name).strip()
            cfg.vm.guest_user = (guest_user.value or cfg.vm.guest_user).strip()
            cfg.gateway.host = (gw_host.value or cfg.gateway.host).strip()
            try:
                cfg.gateway.port = int(gw_port.value or cfg.gateway.port)
            except ValueError:
                pass
            cfg.app.first_run_complete = True
            config_mod.save(cfg)

            if guest_pass.value:
                secrets.set_secret(secrets.VM_USER_PASSWORD, guest_pass.value)
                self.app.vm.guest_password = guest_pass.value
            if gw_pass.value:
                secrets.set_secret(secrets.GATEWAY_PASSWORD, gw_pass.value)
                self.app.gateway.password = gw_pass.value

            self.close()

        def skip(_):
            self.app.config.app.first_run_complete = True
            config_mod.save(self.app.config)
            self.close()

        self._dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Welcome to ClawDeck"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Let's set up the three things ClawDeck needs. "
                            "You can change any of this later in Settings.",
                            size=12,
                        ),
                        ft.Divider(),
                        detected,
                        ft.Text("VM", size=14, weight=ft.FontWeight.W_600),
                        vm_name,
                        ft.Row([guest_user, guest_pass]),
                        ft.Divider(),
                        ft.Text("Gateway", size=14, weight=ft.FontWeight.W_600),
                        ft.Row([gw_host, gw_port]),
                        gw_pass,
                    ],
                    spacing=10,
                    tight=True,
                ),
                width=520,
            ),
            actions=[
                ft.TextButton("Skip", on_click=skip),
                ft.FilledButton("Finish setup", on_click=finish),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.open(self._dialog)

    def close(self) -> None:
        if self._dialog and self._page:
            self._page.close(self._dialog)

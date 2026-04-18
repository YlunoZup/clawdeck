"""Top-level application — wires config, core services, monitor, UI together."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from . import config as config_mod
from . import logging_setup, secrets
from .core.gateway import GatewayClient
from .core.history import HistoryStore
from .core.monitor import Monitor
from .core.origin_sync import OriginSync
from .core.tunnel import TunnelWatcher
from .core.usage import UsageAggregator
from .core.vm import VmController
from .profiles import ProfileStore
from .utils.platform import find_vboxmanage

log = logging.getLogger(__name__)


@dataclass
class App:
    config: config_mod.Config
    profiles: ProfileStore
    vm: VmController
    gateway: GatewayClient
    tunnel: TunnelWatcher
    monitor: Monitor
    history: HistoryStore
    origin_sync: OriginSync
    usage: UsageAggregator

    @classmethod
    def assemble(cls) -> App:
        logging_setup.configure()
        log.info("ClawDeck starting up")

        cfg = config_mod.load()
        profiles = ProfileStore(cfg)

        vbx_path = (
            Path(cfg.vm.vboxmanage_path)
            if cfg.vm.vboxmanage_path
            else find_vboxmanage()
        )

        vm = VmController(
            vm_name=cfg.vm.name,
            vboxmanage_path=vbx_path,
            guest_user=cfg.vm.guest_user,
            guest_password=secrets.get_secret(secrets.VM_USER_PASSWORD),
        )

        gateway = GatewayClient(
            ws_url=cfg.gateway.ws_url,
            http_url=cfg.gateway.http_url,
            password=secrets.get_secret(secrets.GATEWAY_PASSWORD),
            token=secrets.get_secret(secrets.GATEWAY_TOKEN),
            device_label="ClawDeck",
        )

        tunnel = TunnelWatcher(vm=vm, log_path=cfg.tunnel.log_path_on_vm)

        monitor = Monitor(vm=vm, gateway_client=gateway, tunnel=tunnel)
        history = HistoryStore()
        origin_sync = OriginSync(vm=vm)
        usage = UsageAggregator(vm=vm)

        return cls(
            config=cfg,
            profiles=profiles,
            vm=vm,
            gateway=gateway,
            tunnel=tunnel,
            monitor=monitor,
            history=history,
            origin_sync=origin_sync,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def start_stack(self) -> None:
        if self.config.vm.autostart_vm:
            try:
                await self.vm.ensure_running(headless=self.config.vm.headless)
            except Exception as exc:
                log.exception("start_stack vm error: %s", exc)

        try:
            await self.gateway.connect(timeout=10.0)
        except Exception as exc:
            log.info("gateway connect deferred: %s", exc)

    async def stop_stack(self, stop_vm: bool = False) -> None:
        await self.gateway.close()
        if stop_vm:
            try:
                await self.vm.stop(graceful=True)
            except Exception as exc:
                log.warning("stop_stack vm stop error: %s", exc)

    async def send_chat(
        self, message: str, *, session_id: int | None = None,
    ) -> tuple[str, int]:
        """Send ``message``, persist + return (reply_text, session_id)."""
        if session_id is None:
            session = self.history.create_session(title=message[:60] or "New chat")
            session_id = session.id

        self.history.add_message(session_id, "user", message)

        if self.gateway.state.name != "CONNECTED":
            await self.gateway.connect(timeout=10.0)

        reply = await self.gateway.send_message(message)
        self.history.add_message(
            session_id, "agent", reply,
            model=self.monitor.state.agent.model,
        )
        self.monitor.record_agent_reply()
        return reply, session_id

    def get_dashboard_url(self) -> str | None:
        return self.monitor.state.tunnel_url

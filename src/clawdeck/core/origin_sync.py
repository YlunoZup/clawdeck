"""Auto-sync ``gateway.controlUi.allowedOrigins`` when the tunnel URL rotates.

Cloudflare quick-tunnels get a fresh random subdomain every time `cloudflared`
restarts. Without this sync, opening the tunnel URL in a browser after a
rotation shows "origin not allowed" until the user manually updates the
gateway config + restarts it.

This module observes tunnel-URL changes from the monitor and idempotently
pushes the current URL into the gateway config, then hot-restarts the gateway.
"""

from __future__ import annotations

import asyncio
import logging

from ..models import AppState, TunnelState
from .vm import VmController, VmError

log = logging.getLogger(__name__)


class OriginSync:
    def __init__(self, vm: VmController):
        self.vm = vm
        self._lock = asyncio.Lock()
        self._last_synced: str | None = None

    async def maybe_sync(self, state: AppState) -> bool:
        """If the tunnel URL changed, push to gateway config. Returns True on sync."""
        url = state.tunnel_url
        if not url:
            return False
        if state.tunnel not in {TunnelState.UP, TunnelState.ROTATING}:
            return False
        if url == self._last_synced:
            return False

        async with self._lock:
            if url == self._last_synced:
                return False   # another coroutine beat us to it

            ok = await self._push(url)
            if ok:
                self._last_synced = url
            return ok

    async def _push(self, url: str) -> bool:
        if not self.vm.guest_password:
            log.debug("origin sync skipped: no guest password")
            return False

        # Set allowedOrigins
        script = (
            f"openclaw config set gateway.controlUi.allowedOrigins "
            f"'[\\\"{url}\\\"]' >/dev/null && "
            f"echo {self.vm.guest_password} | sudo -S -p '' systemctl restart openclaw-gateway"
        )
        try:
            await self.vm.guest_exec(script, timeout=30.0, allow_fail=True)
            log.info("origin sync: allowedOrigins updated to %s", url)
            return True
        except VmError as exc:
            log.warning("origin sync failed: %s", exc)
            return False

"""Cloudflare tunnel URL watcher.

Cloudflare *quick tunnels* rotate the random ``*.trycloudflare.com`` subdomain
every time the `cloudflared` process restarts. The watcher:

1. Reads the most recent URL from ``/var/log/openclaw-tunnel.log`` inside the VM
   via VBoxManage guestcontrol.
2. If it differs from the last-seen URL, returns the new one so the monitor loop
   can update the gateway's ``controlUi.allowedOrigins`` config.

We also probe the URL over HTTPS to confirm Cloudflare edge is actually routing
traffic — a freshly-spawned tunnel log entry can briefly precede the edge
becoming live.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from ..models import TunnelState
from .vm import VmController, VmError

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)


@dataclass
class TunnelStatus:
    url: str | None
    state: TunnelState
    reachable: bool = False


class TunnelWatcher:
    def __init__(
        self,
        vm: VmController,
        log_path: str = "/var/log/openclaw-tunnel.log",
    ):
        self.vm = vm
        self.log_path = log_path
        self._last_url: str | None = None

    async def detect_url(self) -> str | None:
        """Grab the newest URL from the guest log; falls back to journalctl."""
        script = (
            f"grep -oE 'https://[a-z0-9-]+\\.trycloudflare\\.com' "
            f"{self.log_path} 2>/dev/null | tail -1"
        )
        try:
            out = await self.vm.guest_exec(script, allow_fail=True)
        except VmError as exc:
            log.debug("tunnel detect via file failed: %s", exc)
            out = ""

        out = (out or "").strip()
        if URL_RE.fullmatch(out):
            return out

        # Fallback: journalctl
        fallback = (
            "echo {pw} | sudo -S -p '' journalctl -u openclaw-tunnel "
            "--no-pager -n 200 2>/dev/null | "
            "grep -oE 'https://[a-z0-9-]+\\.trycloudflare\\.com' | tail -1"
        )
        if self.vm.guest_password:
            try:
                out = await self.vm.guest_exec(
                    fallback.format(pw=self.vm.guest_password), allow_fail=True
                )
                out = (out or "").strip()
                if URL_RE.fullmatch(out):
                    return out
            except VmError as exc:
                log.debug("tunnel detect via journalctl failed: %s", exc)

        return None

    async def probe(self, url: str, timeout: float = 8.0) -> bool:
        """Probe the tunnel URL. Any non-5xx response means the edge + origin
        are both serving. We try GET (rather than HEAD) because some gateways
        return 405 on HEAD but 200 on GET.
        """
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                verify=True,
                headers={"User-Agent": "ClawDeck/0.1"},
            ) as c:
                r = await c.get(url, follow_redirects=True)
                return r.status_code < 500
        except (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.NetworkError,
            httpx.HTTPError,
        ) as exc:
            log.debug("tunnel probe failed: %s", exc)
            return False

    async def status(self) -> TunnelStatus:
        url = await self.detect_url()
        if not url:
            return TunnelStatus(url=None, state=TunnelState.DOWN)

        reachable = await self.probe(url)
        state = TunnelState.UP if reachable else TunnelState.DOWN

        if self._last_url and url != self._last_url:
            log.info("tunnel URL rotated: %s → %s", self._last_url, url)
            state = TunnelState.ROTATING
        self._last_url = url

        return TunnelStatus(url=url, state=state, reachable=reachable)

"""Tailscale integration.

Shells out to the local ``tailscale`` CLI to enumerate nodes in the user's
tailnet, determine which (if any) are advertising as exit nodes, and report
the current node's exit-node setting.

Runs on the **host** (not inside the VM) — the exit node typically lives
elsewhere (e.g. the user's Raspberry Pi) and the host's ``tailscaled`` is the
right source of truth for tailnet state.

Parses ``tailscale status --json``, which is stable and has been since 2022.
Older installs without ``--json`` return empty ``TailnetSnapshot``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..utils.platform import is_windows

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class TailnetPeer:
    id: str
    hostname: str
    dns_name: str
    addresses: list[str]
    online: bool
    os: str = ""
    is_exit_node: bool = False
    is_exit_node_option: bool = False
    tags: list[str] = field(default_factory=list)


@dataclass
class TailnetSnapshot:
    tailscale_installed: bool = False
    backend_state: str = "unknown"   # Running | Stopped | NeedsLogin | …
    current_node: TailnetPeer | None = None
    peers: list[TailnetPeer] = field(default_factory=list)
    exit_node_id: str | None = None  # the peer we're currently tunneling through

    @property
    def online_peers(self) -> list[TailnetPeer]:
        return [p for p in self.peers if p.online]

    @property
    def exit_node_candidates(self) -> list[TailnetPeer]:
        return [p for p in self.peers if p.is_exit_node_option]


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class TailscaleController:
    """Async wrapper around the ``tailscale`` CLI on the host."""

    def __init__(self, executable: Path | None = None):
        self._exe: Path | None = executable or _find_tailscale()

    @property
    def available(self) -> bool:
        return self._exe is not None

    @property
    def executable(self) -> Path | None:
        return self._exe

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def status(self) -> TailnetSnapshot:
        snap = TailnetSnapshot(tailscale_installed=bool(self._exe))
        if not self._exe:
            return snap

        out = await self._run("status", "--json")
        if out is None:
            return snap
        try:
            data = json.loads(out)
        except ValueError:
            log.debug("tailscale status returned non-JSON")
            return snap

        snap.backend_state = str(data.get("BackendState", "unknown"))
        snap.exit_node_id = data.get("ExitNodeStatus", {}).get("ID") or None

        self_raw = data.get("Self") or {}
        if self_raw:
            snap.current_node = _peer_from_raw(self_raw)

        peers_raw = data.get("Peer") or {}
        for pid, p in peers_raw.items():
            snap.peers.append(_peer_from_raw({"ID": pid, **p}))

        return snap

    async def set_exit_node(self, peer_id_or_hostname: str | None) -> bool:
        """Route traffic through ``peer_id_or_hostname`` (pass ``None`` to
        disable). Returns True on apparent success.
        """
        if not self._exe:
            return False
        if peer_id_or_hostname:
            out = await self._run("up", f"--exit-node={peer_id_or_hostname}")
        else:
            out = await self._run("up", "--exit-node=")
        return out is not None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run(self, *args: str, timeout: float = 15.0) -> str | None:
        assert self._exe is not None
        cmd = [str(self._exe), *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if is_windows() else 0
                ),
            )
            out, err = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except (OSError, TimeoutError) as exc:
            log.debug("tailscale exec failed: %s", exc)
            return None
        if proc.returncode != 0:
            log.debug(
                "tailscale %s exited %s: %s",
                args[0] if args else "?",
                proc.returncode,
                err.decode(errors="replace")[:200],
            )
            return None
        return out.decode(errors="replace")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_tailscale() -> Path | None:
    # PATH first
    found = shutil.which("tailscale")
    if found:
        return Path(found)

    # Common install paths
    candidates: list[Path] = []
    if is_windows():
        pf = r"C:\Program Files\Tailscale"
        candidates.append(Path(pf) / "tailscale.exe")
    else:
        candidates += [
            Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale"),
            Path("/usr/bin/tailscale"),
            Path("/usr/local/bin/tailscale"),
        ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _peer_from_raw(raw: dict) -> TailnetPeer:
    return TailnetPeer(
        id=str(raw.get("ID", "")),
        hostname=str(raw.get("HostName", "")),
        dns_name=str(raw.get("DNSName", "")),
        addresses=list(raw.get("TailscaleIPs", []) or []),
        online=bool(raw.get("Online", False)),
        os=str(raw.get("OS", "")),
        is_exit_node=bool(raw.get("ExitNode", False)),
        is_exit_node_option=bool(raw.get("ExitNodeOption", False)),
        tags=list(raw.get("Tags", []) or []),
    )

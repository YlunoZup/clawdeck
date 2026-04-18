"""Data models and enums for ClawDeck app state.

All state is expressed here so UI, monitor loop, and services can share a
single contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class VmState(StrEnum):
    """VM lifecycle states, aligned with VBoxManage `VMState` output."""

    RUNNING = "running"
    STOPPED = "stopped"   # aka poweroff
    PAUSED = "paused"
    SAVED = "saved"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"

    @classmethod
    def from_vbox(cls, s: str) -> VmState:
        """Map VBoxManage state strings → enum."""
        s = (s or "").strip().lower()
        mapping = {
            "running": cls.RUNNING,
            "poweroff": cls.STOPPED,
            "aborted": cls.STOPPED,
            "paused": cls.PAUSED,
            "saved": cls.SAVED,
            "starting": cls.STARTING,
            "stopping": cls.STOPPING,
        }
        return mapping.get(s, cls.UNKNOWN)


class GatewayState(StrEnum):
    UNKNOWN = "unknown"
    UNREACHABLE = "unreachable"
    AUTH_REQUIRED = "auth_required"
    PAIRING_REQUIRED = "pairing_required"
    CONNECTED = "connected"
    ERROR = "error"


class TunnelState(StrEnum):
    UNKNOWN = "unknown"
    DOWN = "down"
    UP = "up"
    ROTATING = "rotating"


class OverallHealth(StrEnum):
    """Colour the tray icon uses."""

    HEALTHY = "healthy"       # green
    DEGRADED = "degraded"     # yellow (some component warming up)
    UNHEALTHY = "unhealthy"   # red
    OFFLINE = "offline"       # grey (user stopped everything)


@dataclass
class AppError:
    code: str
    message: str
    when: datetime = field(default_factory=datetime.now)
    actionable: bool = False


@dataclass
class AgentSnapshot:
    model: str | None = None
    provider: str | None = None
    last_reply_at: datetime | None = None
    tokens_in_today: int = 0
    tokens_out_today: int = 0


@dataclass
class AppState:
    vm: VmState = VmState.UNKNOWN
    gateway: GatewayState = GatewayState.UNKNOWN
    tunnel: TunnelState = TunnelState.UNKNOWN
    tunnel_url: str | None = None
    agent: AgentSnapshot = field(default_factory=AgentSnapshot)
    errors: list[AppError] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)

    def overall(self) -> OverallHealth:
        """Derive a single colour from component states."""
        if (
            self.vm == VmState.STOPPED
            and self.gateway == GatewayState.UNKNOWN
        ):
            return OverallHealth.OFFLINE
        if (
            self.vm == VmState.RUNNING
            and self.gateway == GatewayState.CONNECTED
            and self.tunnel == TunnelState.UP
        ):
            return OverallHealth.HEALTHY
        if self.gateway in {GatewayState.ERROR, GatewayState.UNREACHABLE}:
            return OverallHealth.UNHEALTHY
        return OverallHealth.DEGRADED


@dataclass(frozen=True)
class ChatMessage:
    role: str           # "user" | "agent" | "system"
    text: str
    when: datetime = field(default_factory=datetime.now)

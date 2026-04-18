"""Remote federation scaffolding.

A *federation* is a set of gateway endpoints the user wants to reach from one
ClawDeck. Each node has its own auth, monitor, and chat history (scoped by
profile). Phase 3 ships the data model + a minimal switcher; the full UI
(parallel chat panes, cross-node search) lands incrementally.

Design:
- Each profile owns a ``FederationNode`` describing how to reach its gateway.
- The active profile is *the* gateway (Phase 3 single-active). Phase 4 can
  keep multiple nodes warm and run parallel conversations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .core.gateway import GatewayClient

log = logging.getLogger(__name__)


@dataclass
class FederationNode:
    """One reachable OpenClaw gateway."""

    profile_id: str
    display_name: str
    ws_url: str
    http_url: str
    password: str | None = None
    token: str | None = None
    tags: list[str] = field(default_factory=list)

    def build_client(self) -> GatewayClient:
        return GatewayClient(
            ws_url=self.ws_url,
            http_url=self.http_url,
            password=self.password,
            token=self.token,
            device_label=f"ClawDeck [{self.display_name}]",
        )


class Federation:
    """In-memory set of known nodes with an active pointer."""

    def __init__(self) -> None:
        self._nodes: dict[str, FederationNode] = {}
        self._active: str | None = None

    def add(self, node: FederationNode) -> None:
        self._nodes[node.profile_id] = node
        if self._active is None:
            self._active = node.profile_id

    def remove(self, profile_id: str) -> None:
        self._nodes.pop(profile_id, None)
        if self._active == profile_id:
            self._active = next(iter(self._nodes), None)

    def switch(self, profile_id: str) -> FederationNode:
        if profile_id not in self._nodes:
            raise KeyError(profile_id)
        self._active = profile_id
        return self._nodes[profile_id]

    @property
    def active(self) -> FederationNode | None:
        return self._nodes.get(self._active) if self._active else None

    def all(self) -> list[FederationNode]:
        return list(self._nodes.values())

    def __len__(self) -> int:
        return len(self._nodes)

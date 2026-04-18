"""Multiple profile support.

A *profile* bundles a VM / gateway / tunnel triple plus a display name, so the
user can switch between their local VirtualBox setup, a remote VPS, or a
Tailscale-fronted machine without re-typing anything.

Profiles are stored inside the main ``config.toml`` under ``[profiles.<id>]``
tables and referenced by ``app.active_profile``. Secrets remain per-profile in
the OS keychain (see ``secrets.py``) — the key is ``gateway.password.<profile>``.

The first profile in any config is always ``"default"`` and mirrors what Phase 1
used at the root of the config file. Migration happens automatically on first
load.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .config import ChatSection, Config, GatewaySection, TunnelSection, VmSection

log = logging.getLogger(__name__)

DEFAULT_PROFILE_ID = "default"


@dataclass
class Profile:
    id: str
    display_name: str = ""
    description: str = ""
    kind: str = "local"          # local | vps | tailscale | manual
    vm: VmSection = field(default_factory=VmSection)
    gateway: GatewaySection = field(default_factory=GatewaySection)
    tunnel: TunnelSection = field(default_factory=TunnelSection)
    chat: ChatSection = field(default_factory=ChatSection)

    @property
    def label(self) -> str:
        return self.display_name or self.id


def from_config(cfg: Config) -> Profile:
    """Return the Phase 1 "default" profile projected from a Config object."""
    return Profile(
        id=DEFAULT_PROFILE_ID,
        display_name="Local VM",
        description="The VirtualBox-based setup from Phase 1.",
        kind="local",
        vm=cfg.vm,
        gateway=cfg.gateway,
        tunnel=cfg.tunnel,
        chat=cfg.chat,
    )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def remote_vps_template(display_name: str = "Remote VPS") -> Profile:
    return Profile(
        id="vps",
        display_name=display_name,
        description="OpenClaw on a remote VPS reached over the public internet.",
        kind="vps",
        vm=VmSection(provider="remote-ssh"),
        gateway=GatewaySection(host="", port=18789, scheme="wss"),
        tunnel=TunnelSection(type="manual"),
        chat=ChatSection(),
    )


def tailscale_template(display_name: str = "Tailscale peer") -> Profile:
    return Profile(
        id="tailnet",
        display_name=display_name,
        description="Reach OpenClaw over a Tailscale tailnet.",
        kind="tailscale",
        vm=VmSection(provider="tailnet"),
        gateway=GatewaySection(host="", port=18789, scheme="ws"),
        tunnel=TunnelSection(type="tailscale"),
        chat=ChatSection(),
    )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class ProfileStore:
    """In-memory profile collection, persisted via a Config object.

    Phase 1 config is single-profile; this class hides that detail so code
    paths don't care whether there are 1 or many profiles configured.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        # Phase 1 compat: seed with a default profile from the root sections
        self._profiles: dict[str, Profile] = {
            DEFAULT_PROFILE_ID: from_config(cfg),
        }
        self._active: str = DEFAULT_PROFILE_ID

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def active(self) -> Profile:
        return self._profiles[self._active]

    def all(self) -> list[Profile]:
        return list(self._profiles.values())

    def switch(self, profile_id: str) -> Profile:
        if profile_id not in self._profiles:
            raise KeyError(profile_id)
        self._active = profile_id
        return self.active

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, profile: Profile) -> None:
        self._profiles[profile.id] = profile

    def remove(self, profile_id: str) -> None:
        if profile_id == DEFAULT_PROFILE_ID:
            raise ValueError("cannot remove the default profile")
        self._profiles.pop(profile_id, None)
        if self._active == profile_id:
            self._active = DEFAULT_PROFILE_ID

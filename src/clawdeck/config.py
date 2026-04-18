"""Config file loading and persistence.

TOML-backed, schema-validated, writable. Secrets live separately in `secrets.py`
(keyring/Credential Manager) and are *never* written to this file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

try:
    import tomllib
except ImportError:  # pragma: no cover — py<3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]

import contextlib

from .utils.paths import config_file

log = logging.getLogger(__name__)


@dataclass
class AppSection:
    theme: str = "auto"                # auto | light | dark
    autostart: bool = True
    check_updates: bool = True
    first_run_complete: bool = False


@dataclass
class VmSection:
    name: str = "OpenClaw"
    provider: str = "virtualbox"
    headless: bool = True
    autostart_vm: bool = True
    vboxmanage_path: str = ""          # empty → auto-detect
    guest_user: str = "vboxuser"


@dataclass
class GatewaySection:
    host: str = "127.0.0.1"
    port: int = 18789
    scheme: str = "ws"
    tls_verify: bool = True

    @property
    def ws_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def http_url(self) -> str:
        scheme = "https" if self.scheme == "wss" else "http"
        return f"{scheme}://{self.host}:{self.port}"


@dataclass
class TunnelSection:
    type: str = "cloudflared"          # cloudflared | tailscale | manual
    detect_from_vm: bool = True
    fallback_url: str = ""
    log_path_on_vm: str = "/var/log/openclaw-tunnel.log"


@dataclass
class ChatSection:
    persist_history: bool = True
    history_dir: str = ""              # empty → platform default


@dataclass
class Config:
    app: AppSection = field(default_factory=AppSection)
    vm: VmSection = field(default_factory=VmSection)
    gateway: GatewaySection = field(default_factory=GatewaySection)
    tunnel: TunnelSection = field(default_factory=TunnelSection)
    chat: ChatSection = field(default_factory=ChatSection)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_toml_dict(self) -> dict:
        return {
            "app": vars(self.app),
            "vm": vars(self.vm),
            "gateway": {
                k: v for k, v in vars(self.gateway).items()
                if not k.startswith("_")
            },
            "tunnel": vars(self.tunnel),
            "chat": vars(self.chat),
        }

    @classmethod
    def from_toml_dict(cls, data: dict) -> Config:
        def pick(section: dict, key: str, default):
            return section.get(key, default)

        app_data = data.get("app", {})
        vm_data = data.get("vm", {})
        gw_data = data.get("gateway", {})
        tn_data = data.get("tunnel", {})
        ch_data = data.get("chat", {})

        return cls(
            app=AppSection(
                theme=pick(app_data, "theme", "auto"),
                autostart=pick(app_data, "autostart", True),
                check_updates=pick(app_data, "check_updates", True),
                first_run_complete=pick(app_data, "first_run_complete", False),
            ),
            vm=VmSection(
                name=pick(vm_data, "name", "OpenClaw"),
                provider=pick(vm_data, "provider", "virtualbox"),
                headless=pick(vm_data, "headless", True),
                autostart_vm=pick(vm_data, "autostart_vm", True),
                vboxmanage_path=pick(vm_data, "vboxmanage_path", ""),
                guest_user=pick(vm_data, "guest_user", "vboxuser"),
            ),
            gateway=GatewaySection(
                host=pick(gw_data, "host", "127.0.0.1"),
                port=int(pick(gw_data, "port", 18789)),
                scheme=pick(gw_data, "scheme", "ws"),
                tls_verify=pick(gw_data, "tls_verify", True),
            ),
            tunnel=TunnelSection(
                type=pick(tn_data, "type", "cloudflared"),
                detect_from_vm=pick(tn_data, "detect_from_vm", True),
                fallback_url=pick(tn_data, "fallback_url", ""),
                log_path_on_vm=pick(
                    tn_data,
                    "log_path_on_vm",
                    "/var/log/openclaw-tunnel.log",
                ),
            ),
            chat=ChatSection(
                persist_history=pick(ch_data, "persist_history", True),
                history_dir=pick(ch_data, "history_dir", ""),
            ),
        )


# ---------------------------------------------------------------------------
# Load / save entry points
# ---------------------------------------------------------------------------

def load(path: Path | None = None) -> Config:
    """Load config from disk, creating defaults if missing."""
    p = path or config_file()
    if not p.exists():
        log.info("No config at %s, writing defaults", p)
        cfg = Config()
        save(cfg, p)
        return cfg
    try:
        with p.open("rb") as f:
            data = tomllib.load(f)
        return Config.from_toml_dict(data)
    except Exception as exc:
        log.exception("Config parse failed, falling back to defaults: %s", exc)
        # Back up the broken file so the user can inspect later.
        with contextlib.suppress(OSError):
            p.rename(p.with_suffix(".toml.broken"))
        cfg = Config()
        save(cfg, p)
        return cfg


def save(cfg: Config, path: Path | None = None) -> None:
    p = path or config_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("wb") as f:
        tomli_w.dump(cfg.to_toml_dict(), f)
    log.debug("Config saved to %s", p)

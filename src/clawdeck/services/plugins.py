"""Plugin system.

Plugins are plain Python files placed in ``~/.clawdeck/plugins/`` (the
``data_dir()/plugins`` path). Each plugin module may expose a ``plugin``
attribute implementing the ``Plugin`` protocol. ClawDeck discovers, loads,
and calls lifecycle hooks on every plugin at startup.

Design goals:
- **Sandboxed by obscurity, not hard sandbox.** Plugins run in-process; the
  user is trusting them. We log what gets loaded and provide a Settings toggle
  to disable them globally.
- **Narrow API.** Plugins can register extra tabs, tray menu entries, and
  state-change callbacks. No arbitrary monkeypatching encouraged.
- **Fault tolerant.** A raising plugin is logged + quarantined; the rest of
  ClawDeck keeps running.

Example plugin (saved as ``~/.clawdeck/plugins/hello.py``):

    from clawdeck.services.plugins import Plugin, PluginContext

    class HelloPlugin(Plugin):
        name = "hello"
        description = "Says hi on startup"

        def on_startup(self, ctx: PluginContext) -> None:
            print("Hello from my plugin!")

    plugin = HelloPlugin()
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from ..utils.paths import data_dir

if TYPE_CHECKING:
    from ..app import App
    from ..models import AppState

log = logging.getLogger(__name__)


def plugins_dir() -> Path:
    p = data_dir() / "plugins"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@dataclass
class PluginContext:
    """What plugins can reach. Kept intentionally small."""

    app: App
    # Plugins can read the latest state. Mutating is not supported.
    state_snapshot: Any = None

    def notify(self, title: str, body: str) -> None:
        from .notify import Notification, send
        send(Notification(title=title, body=body))


@runtime_checkable
class Plugin(Protocol):
    name: str
    description: str

    def on_startup(self, ctx: PluginContext) -> None: ...
    def on_state(self, state: AppState, ctx: PluginContext) -> None: ...
    def on_shutdown(self, ctx: PluginContext) -> None: ...


class BasePlugin:
    """Convenience base class with default no-op hooks."""

    name: str = "unnamed"
    description: str = ""

    def on_startup(self, ctx: PluginContext) -> None:
        pass

    def on_state(self, state: AppState, ctx: PluginContext) -> None:
        pass

    def on_shutdown(self, ctx: PluginContext) -> None:
        pass


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


@dataclass
class LoadedPlugin:
    name: str
    description: str
    source: Path
    instance: Plugin
    errors: list[str] = field(default_factory=list)


class PluginManager:
    """Discovers + loads plugins, dispatches lifecycle hooks."""

    def __init__(self, app: App, enabled: bool = True):
        self.app = app
        self.enabled = enabled
        self._plugins: list[LoadedPlugin] = []

    @property
    def loaded(self) -> list[LoadedPlugin]:
        return list(self._plugins)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[LoadedPlugin]:
        self._plugins = []
        if not self.enabled:
            return self._plugins

        d = plugins_dir()
        for path in sorted(d.glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                inst = self._import_one(path)
                if inst is not None:
                    self._plugins.append(
                        LoadedPlugin(
                            name=getattr(inst, "name", path.stem),
                            description=getattr(inst, "description", ""),
                            source=path,
                            instance=inst,
                        )
                    )
            except Exception as exc:  # pragma: no cover — hostile plugin
                log.exception("plugin %s import failed", path.name)
                self._plugins.append(
                    LoadedPlugin(
                        name=path.stem, description="",
                        source=path, instance=BasePlugin(),  # type: ignore[arg-type]
                        errors=[f"import failed: {exc}"],
                    )
                )
        log.info("loaded %d plugin(s)", len(self._plugins))
        return self._plugins

    def _import_one(self, path: Path) -> Plugin | None:
        module_name = f"clawdeck_plugin_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)

        inst = getattr(mod, "plugin", None)
        if inst is None:
            log.warning("plugin %s has no `plugin` attribute; skipping", path.name)
            return None
        if not isinstance(inst, Plugin):
            log.warning(
                "plugin %s does not implement the Plugin protocol; skipping",
                path.name,
            )
            return None
        return inst

    # ------------------------------------------------------------------
    # Lifecycle dispatch
    # ------------------------------------------------------------------

    def _ctx(self, state: AppState | None = None) -> PluginContext:
        return PluginContext(app=self.app, state_snapshot=state)

    def on_startup(self) -> None:
        for p in self._plugins:
            try:
                p.instance.on_startup(self._ctx())
            except Exception as exc:
                log.exception("plugin %s on_startup raised", p.name)
                p.errors.append(f"on_startup: {exc}")

    def on_state(self, state: AppState) -> None:
        for p in self._plugins:
            try:
                p.instance.on_state(state, self._ctx(state))
            except Exception as exc:
                log.exception("plugin %s on_state raised", p.name)
                p.errors.append(f"on_state: {exc}")

    def on_shutdown(self) -> None:
        for p in self._plugins:
            try:
                p.instance.on_shutdown(self._ctx())
            except Exception as exc:
                log.exception("plugin %s on_shutdown raised", p.name)
                p.errors.append(f"on_shutdown: {exc}")

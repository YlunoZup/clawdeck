"""Plugin manager tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from clawdeck.services.plugins import PluginManager, plugins_dir


def _good_plugin_source() -> str:
    return """
from clawdeck.services.plugins import BasePlugin

class HelloPlugin(BasePlugin):
    name = "hello"
    description = "says hi"

    def on_startup(self, ctx):
        ctx.app._plugin_startup_called = True

plugin = HelloPlugin()
"""


def _bad_plugin_source() -> str:
    return "raise RuntimeError('boom on import')\n"


def _no_instance_plugin() -> str:
    return "# no `plugin` attribute\n"


def test_plugin_discovery_and_dispatch(tmp_path, monkeypatch):
    # Redirect plugins_dir() to tmp_path
    monkeypatch.setattr(
        "clawdeck.services.plugins.plugins_dir", lambda: tmp_path
    )

    (tmp_path / "hello.py").write_text(_good_plugin_source())

    app_mock = MagicMock()
    mgr = PluginManager(app_mock, enabled=True)
    loaded = mgr.discover()

    assert len(loaded) == 1
    assert loaded[0].name == "hello"

    mgr.on_startup()
    assert app_mock._plugin_startup_called is True


def test_disabled_manager_loads_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "clawdeck.services.plugins.plugins_dir", lambda: tmp_path
    )
    (tmp_path / "hello.py").write_text(_good_plugin_source())
    mgr = PluginManager(MagicMock(), enabled=False)
    assert mgr.discover() == []


def test_skip_leading_underscore(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "clawdeck.services.plugins.plugins_dir", lambda: tmp_path
    )
    (tmp_path / "_private.py").write_text(_good_plugin_source())
    mgr = PluginManager(MagicMock(), enabled=True)
    assert mgr.discover() == []


def test_missing_plugin_attr_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "clawdeck.services.plugins.plugins_dir", lambda: tmp_path
    )
    (tmp_path / "nope.py").write_text(_no_instance_plugin())
    mgr = PluginManager(MagicMock(), enabled=True)
    loaded = mgr.discover()
    assert loaded == []


def test_plugin_raising_on_startup_does_not_kill_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "clawdeck.services.plugins.plugins_dir", lambda: tmp_path
    )
    (tmp_path / "hello.py").write_text(
        """
from clawdeck.services.plugins import BasePlugin

class HelloPlugin(BasePlugin):
    name = "hello"
    description = "breaks"
    def on_startup(self, ctx):
        raise RuntimeError("boom")

plugin = HelloPlugin()
"""
    )
    mgr = PluginManager(MagicMock(), enabled=True)
    mgr.discover()
    mgr.on_startup()
    assert "on_startup: boom" in mgr.loaded[0].errors[0]


def test_plugins_dir_exists():
    p = plugins_dir()
    assert isinstance(p, Path)
    assert p.exists()

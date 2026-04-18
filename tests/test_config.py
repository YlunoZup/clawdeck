"""Config load/save round-trip tests."""

from __future__ import annotations

from pathlib import Path

from clawdeck import config as config_mod


def test_defaults_create_file(tmp_path: Path):
    cfg_path = tmp_path / "config.toml"
    cfg = config_mod.load(cfg_path)
    assert cfg.app.theme == "auto"
    assert cfg.vm.name == "OpenClaw"
    assert cfg_path.exists()


def test_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "config.toml"
    cfg = config_mod.Config()
    cfg.app.theme = "dark"
    cfg.vm.name = "MyVM"
    cfg.gateway.port = 20000
    config_mod.save(cfg, cfg_path)

    loaded = config_mod.load(cfg_path)
    assert loaded.app.theme == "dark"
    assert loaded.vm.name == "MyVM"
    assert loaded.gateway.port == 20000


def test_broken_file_is_backed_up(tmp_path: Path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("!!! not toml !!!", encoding="utf-8")

    cfg = config_mod.load(cfg_path)
    # Should fall back to defaults
    assert cfg.vm.name == "OpenClaw"
    # Broken file preserved under .broken
    assert cfg_path.with_suffix(".toml.broken").exists()


def test_ws_url_property():
    cfg = config_mod.Config()
    cfg.gateway.host = "example.local"
    cfg.gateway.port = 1234
    assert cfg.gateway.ws_url == "ws://example.local:1234"
    assert cfg.gateway.http_url == "http://example.local:1234"

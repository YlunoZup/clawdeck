"""Profile store tests."""

from __future__ import annotations

import pytest

from clawdeck.config import Config
from clawdeck.profiles import (
    DEFAULT_PROFILE_ID,
    ProfileStore,
    remote_vps_template,
)


def test_default_profile_from_config():
    cfg = Config()
    store = ProfileStore(cfg)
    assert store.active.id == DEFAULT_PROFILE_ID
    assert store.active.vm.name == cfg.vm.name


def test_add_and_switch():
    store = ProfileStore(Config())
    store.add(remote_vps_template())
    ids = {p.id for p in store.all()}
    assert ids == {DEFAULT_PROFILE_ID, "vps"}
    p = store.switch("vps")
    assert p.id == "vps"
    assert store.active.kind == "vps"


def test_remove_nondefault():
    store = ProfileStore(Config())
    store.add(remote_vps_template())
    store.switch("vps")
    store.remove("vps")
    assert {p.id for p in store.all()} == {DEFAULT_PROFILE_ID}
    assert store.active.id == DEFAULT_PROFILE_ID


def test_cannot_remove_default():
    store = ProfileStore(Config())
    with pytest.raises(ValueError):
        store.remove(DEFAULT_PROFILE_ID)


def test_switch_unknown_raises():
    store = ProfileStore(Config())
    with pytest.raises(KeyError):
        store.switch("nope")

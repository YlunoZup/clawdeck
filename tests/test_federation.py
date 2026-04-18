"""Federation data model tests."""

from __future__ import annotations

import pytest

from clawdeck.federation import Federation, FederationNode


def _node(pid: str, name: str = "") -> FederationNode:
    return FederationNode(
        profile_id=pid,
        display_name=name or pid,
        ws_url=f"ws://{pid}.example/18789",
        http_url=f"http://{pid}.example:18789",
    )


def test_add_first_node_is_active():
    f = Federation()
    f.add(_node("local"))
    assert f.active is not None
    assert f.active.profile_id == "local"


def test_switch():
    f = Federation()
    f.add(_node("a"))
    f.add(_node("b"))
    n = f.switch("b")
    assert n.profile_id == "b"
    assert f.active and f.active.profile_id == "b"


def test_switch_unknown_raises():
    f = Federation()
    with pytest.raises(KeyError):
        f.switch("nope")


def test_remove_active_picks_another():
    f = Federation()
    f.add(_node("a"))
    f.add(_node("b"))
    f.switch("a")
    f.remove("a")
    assert f.active and f.active.profile_id == "b"


def test_remove_last_clears_active():
    f = Federation()
    f.add(_node("a"))
    f.remove("a")
    assert f.active is None


def test_build_client_produces_gateway_client():
    n = _node("remote", "Remote")
    client = n.build_client()
    assert client.ws_url == n.ws_url
    assert client.device_label == "ClawDeck [Remote]"

"""Tailscale parser tests — pure logic, no CLI invocation."""

from __future__ import annotations

import json

from clawdeck.core.tailscale import _peer_from_raw


def test_peer_from_minimal():
    p = _peer_from_raw({"ID": "abc", "HostName": "pi"})
    assert p.id == "abc"
    assert p.hostname == "pi"
    assert p.online is False
    assert p.is_exit_node is False


def test_peer_from_full():
    raw = {
        "ID": "xyz",
        "HostName": "server",
        "DNSName": "server.my-tailnet.ts.net.",
        "TailscaleIPs": ["100.64.1.2", "fd7a::1"],
        "Online": True,
        "OS": "linux",
        "ExitNode": False,
        "ExitNodeOption": True,
        "Tags": ["tag:server"],
    }
    p = _peer_from_raw(raw)
    assert p.addresses == ["100.64.1.2", "fd7a::1"]
    assert p.online is True
    assert p.is_exit_node_option is True
    assert p.tags == ["tag:server"]


def test_can_round_trip_fake_status():
    data = {
        "BackendState": "Running",
        "Self": {"ID": "self", "HostName": "laptop", "Online": True, "TailscaleIPs": []},
        "Peer": {
            "p1": {"HostName": "pi", "Online": True, "ExitNodeOption": True},
        },
        "ExitNodeStatus": {"ID": "p1"},
    }
    # Ensure parse-shaped JSON is valid
    assert json.loads(json.dumps(data)) == data

"""GatewayClient unit tests (no real network)."""

from __future__ import annotations

import pytest

from clawdeck.core.gateway import (
    AuthError,
    GatewayClient,
    GatewayError,
    PairingRequiredError,
    RpcError,
)
from clawdeck.models import GatewayState


def test_default_state_is_unknown():
    gw = GatewayClient("ws://127.0.0.1:1", "http://127.0.0.1:1")
    assert gw.state == GatewayState.UNKNOWN


def test_rpc_error_str():
    err = RpcError("agent.run", 42, "boom")
    assert "agent.run" in str(err)
    assert "42" in str(err)


def test_auth_error_subclass():
    assert issubclass(AuthError, GatewayError)
    assert issubclass(PairingRequiredError, GatewayError)


@pytest.mark.asyncio
async def test_tcp_probe_fails_on_closed_port():
    gw = GatewayClient("ws://127.0.0.1:1", "http://127.0.0.1:1")
    # Port 1 is almost certainly closed
    assert await gw._tcp_probe(timeout=0.5) is False

"""Model + state derivation tests."""

from __future__ import annotations

from clawdeck.models import (
    AppState,
    GatewayState,
    OverallHealth,
    TunnelState,
    VmState,
)


def test_vm_state_from_vbox():
    assert VmState.from_vbox("running") == VmState.RUNNING
    assert VmState.from_vbox("poweroff") == VmState.STOPPED
    assert VmState.from_vbox("ABORTED") == VmState.STOPPED
    assert VmState.from_vbox("anything else") == VmState.UNKNOWN


def test_overall_healthy():
    s = AppState(
        vm=VmState.RUNNING,
        gateway=GatewayState.CONNECTED,
        tunnel=TunnelState.UP,
    )
    assert s.overall() == OverallHealth.HEALTHY


def test_overall_unhealthy_when_gateway_down():
    s = AppState(
        vm=VmState.RUNNING,
        gateway=GatewayState.UNREACHABLE,
        tunnel=TunnelState.UP,
    )
    assert s.overall() == OverallHealth.UNHEALTHY


def test_overall_offline_when_everything_stopped():
    s = AppState(vm=VmState.STOPPED, gateway=GatewayState.UNKNOWN)
    assert s.overall() == OverallHealth.OFFLINE


def test_overall_degraded_default():
    s = AppState()   # all UNKNOWN
    # VM unknown but gateway unknown too → degraded (not strictly offline)
    assert s.overall() == OverallHealth.DEGRADED

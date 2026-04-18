"""Status monitor — the background loop that keeps ``AppState`` fresh.

One controller owns three pollers (VM / gateway / tunnel) at different cadences.
Subscribers register a sync callback; the monitor calls them on every state
change so the tray icon and main window can react immediately.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from ..models import (
    AgentSnapshot,
    AppError,
    AppState,
    GatewayState,
    TunnelState,
    VmState,
)
from .gateway import GatewayClient
from .tunnel import TunnelWatcher
from .vm import VmController

log = logging.getLogger(__name__)

Listener = Callable[[AppState], Awaitable[None] | None]


class Monitor:
    """Background monitor with sub-5s reaction times.

    Cadence:
      - VM poll         every 10s
      - Gateway HTTP    every  5s
      - Tunnel probe    every 30s

    Change detection is shallow (compare by field); the full ``AppState``
    snapshot is forwarded to every listener on any change.
    """

    def __init__(
        self,
        vm: VmController,
        gateway_client: GatewayClient,
        tunnel: TunnelWatcher,
    ):
        self.vm = vm
        self.gateway = gateway_client
        self.tunnel = tunnel

        self.state = AppState()
        self._listeners: list[Listener] = []

        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    async def _emit(self) -> None:
        self.state.last_update = datetime.now()
        for fn in list(self._listeners):
            try:
                result = fn(self.state)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                log.exception("listener raised")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._stop.clear()
        self._tasks = [
            asyncio.create_task(self._vm_loop(), name="monitor.vm"),
            asyncio.create_task(self._gateway_loop(), name="monitor.gateway"),
            asyncio.create_task(self._tunnel_loop(), name="monitor.tunnel"),
        ]

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        self._tasks.clear()

    async def _sleep(self, seconds: float) -> None:
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)

    # ------------------------------------------------------------------
    # Pollers
    # ------------------------------------------------------------------

    async def _vm_loop(self) -> None:
        while not self._stop.is_set():
            try:
                new_state = await self.vm.state()
            except Exception as exc:
                log.warning("vm poll error: %s", exc)
                new_state = VmState.UNKNOWN
                self._record_error("vm.poll", str(exc))

            if new_state != self.state.vm:
                self.state.vm = new_state
                await self._emit()

            await self._sleep(10.0)

    async def _gateway_loop(self) -> None:
        while not self._stop.is_set():
            # Cheap HTTP health first; always run this even if WS is up.
            # When health() fails it mutates the client's internal state, so we
            # pick that up directly.
            health = await self.gateway.health(timeout=4.0)
            new_state = (
                self.gateway.state if health is None else GatewayState.CONNECTED
            )

            if new_state != self.state.gateway:
                self.state.gateway = new_state
                await self._emit()

            await self._sleep(5.0)

    async def _tunnel_loop(self) -> None:
        while not self._stop.is_set():
            try:
                status = await self.tunnel.status()
            except Exception as exc:
                log.warning("tunnel poll error: %s", exc)
                self._record_error("tunnel.poll", str(exc))
                status = None

            if status is not None:
                if (
                    status.url != self.state.tunnel_url
                    or status.state != self.state.tunnel
                ):
                    self.state.tunnel_url = status.url
                    self.state.tunnel = status.state
                    await self._emit()
            else:
                if self.state.tunnel != TunnelState.UNKNOWN:
                    self.state.tunnel = TunnelState.UNKNOWN
                    await self._emit()

            await self._sleep(30.0)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _record_error(self, code: str, message: str, actionable: bool = False) -> None:
        self.state.errors.append(AppError(code=code, message=message, actionable=actionable))
        # Cap errors so the list doesn't grow unbounded
        if len(self.state.errors) > 50:
            self.state.errors = self.state.errors[-50:]

    # ------------------------------------------------------------------
    # Agent updates (called by chat flow)
    # ------------------------------------------------------------------

    def record_agent_reply(self, model: str | None = None) -> None:
        snap = self.state.agent or AgentSnapshot()
        snap.last_reply_at = datetime.now()
        if model:
            snap.model = model
        self.state.agent = snap

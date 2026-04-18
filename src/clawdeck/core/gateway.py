"""OpenClaw gateway WebSocket client.

Implements the minimum of OpenClaw's WS RPC protocol that ClawDeck needs:

- ``connect()`` — opens the socket, sends password/token auth
- ``health()`` — GET /health (HTTP) for a cheap liveness probe
- ``call(method, params)`` — fire a single RPC and wait for its reply
- ``send_message(text)`` — agent prompt → reply text
- ``list_pending_devices() / approve_device(id)`` — device pairing helpers

The WS message shape is OpenClaw's native
``{ "type": "req", "id": "<uuid>", "method": "<name>", "params": {...} }``
with matching ``{ "type": "res", "id": "<uuid>", ... }`` replies.

We also sniff a few known "closed before connect" error codes:
- ``1008 pairing required`` → surface ``GatewayState.PAIRING_REQUIRED``
- ``1008 auth required`` → ``AUTH_REQUIRED``
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

# ``_InvalidStatus`` was renamed to ``InvalidStatus`` in websockets 13+;
# older installs still expose the former. Try both.
try:
    from websockets.exceptions import InvalidStatus as _InvalidStatus
except ImportError:   # pragma: no cover
    from websockets.exceptions import _InvalidStatus as _InvalidStatus  # type: ignore[no-redef]

from ..models import GatewayState

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GatewayError(Exception):
    """Base class."""


class AuthError(GatewayError):
    pass


class PairingRequiredError(GatewayError):
    pass


class RpcError(GatewayError):
    def __init__(self, method: str, code: int | str | None, message: str):
        self.method = method
        self.code = code
        self.message = message
        super().__init__(f"{method}: [{code}] {message}")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class HealthResponse:
    status: str
    version: str | None = None
    ready: bool = False


@dataclass
class PendingDevice:
    request_id: str
    device_id: str
    role: str
    scopes: list[str]
    ip: str | None
    flags: list[str]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class GatewayClient:
    def __init__(
        self,
        ws_url: str,
        http_url: str,
        *,
        password: str | None = None,
        token: str | None = None,
        device_label: str = "ClawDeck",
    ):
        self.ws_url = ws_url
        self.http_url = http_url
        self.password = password
        self.token = token
        self.device_label = device_label

        self._ws: websockets.WebSocketClientProtocol | None = None
        self._reader_task: asyncio.Task | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._state: GatewayState = GatewayState.UNKNOWN

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def state(self) -> GatewayState:
        return self._state

    def _set_state(self, s: GatewayState) -> None:
        if s != self._state:
            log.info("gateway state: %s → %s", self._state, s)
            self._state = s

    # ------------------------------------------------------------------
    # HTTP liveness
    # ------------------------------------------------------------------

    async def health(self, timeout: float = 5.0) -> HealthResponse | None:
        """Cheap HTTP liveness probe. Does NOT require auth.

        OpenClaw's gateway answers the dashboard route on ``/`` but may refuse
        non-browser clients on ``/health`` — so we treat "socket connected"
        as the real liveness signal and only upgrade to CONNECTED when we
        actually parse a 200 JSON reply.
        """
        url = f"{self.http_url}/health"
        try:
            async with httpx.AsyncClient(timeout=timeout, verify=False) as c:
                r = await c.get(url)
        except (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
            httpx.NetworkError,
            httpx.HTTPError,
        ) as exc:
            log.debug("health probe failed: %s", exc)
            # Fall back to a raw TCP probe — if the port is open we treat the
            # gateway as alive (auth_required), otherwise unreachable.
            if await self._tcp_probe(timeout=min(timeout, 3.0)):
                self._set_state(GatewayState.AUTH_REQUIRED)
            else:
                self._set_state(GatewayState.UNREACHABLE)
            return None

        if r.status_code == 200:
            try:
                data = r.json()
            except ValueError:
                data = {}
            return HealthResponse(
                status=str(data.get("status", "ok")),
                version=data.get("version"),
                ready=bool(data.get("ready", True)),
            )
        if r.status_code in (401, 403):
            self._set_state(GatewayState.AUTH_REQUIRED)
        return None

    async def _tcp_probe(self, timeout: float = 3.0) -> bool:
        """Plain TCP connect check — port open means the gateway is up."""
        # Derive host/port from the ws URL.
        from urllib.parse import urlparse
        u = urlparse(self.ws_url)
        host = u.hostname or "127.0.0.1"
        port = u.port or 18789
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True
        except (OSError, TimeoutError):
            return False

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------

    async def connect(self, timeout: float = 10.0) -> None:
        """Open the WS and wait for the auth handshake to settle."""
        if self._ws and not self._ws.closed:
            return

        log.info("Connecting to %s", self.ws_url)
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    self.ws_url,
                    open_timeout=timeout,
                    ping_interval=30,
                    ping_timeout=10,
                    max_size=None,
                ),
                timeout=timeout,
            )
        except (TimeoutError, OSError, _InvalidStatus) as exc:
            self._set_state(GatewayState.UNREACHABLE)
            raise GatewayError(f"Could not reach gateway: {exc}") from exc

        self._reader_task = asyncio.create_task(self._reader_loop())

        # Auth immediately after open; OpenClaw expects an early `connect`
        # request with credentials.
        try:
            await self._auth_handshake()
        except PairingRequiredError:
            self._set_state(GatewayState.PAIRING_REQUIRED)
            raise
        except AuthError:
            self._set_state(GatewayState.AUTH_REQUIRED)
            raise

        self._set_state(GatewayState.CONNECTED)

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[GatewayClient]:
        try:
            await self.connect()
            yield self
        finally:
            await self.close()

    # ------------------------------------------------------------------
    # Low-level RPC
    # ------------------------------------------------------------------

    async def _send_raw(self, obj: dict[str, Any]) -> None:
        if not self._ws:
            raise GatewayError("Not connected")
        await self._ws.send(json.dumps(obj))

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        if not self._ws:
            raise GatewayError("Not connected")

        req_id = uuid.uuid4().hex
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut

        await self._send_raw({
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params or {},
        })
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise RpcError(method, "timeout", f"No reply in {timeout}s") from exc

    # ------------------------------------------------------------------
    # Reader
    # ------------------------------------------------------------------

    async def _reader_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except ValueError:
                    log.warning("malformed ws frame: %r", raw[:200])
                    continue
                self._dispatch(msg)
        except ConnectionClosed as exc:
            log.info("gateway closed: %s", exc)
            reason = (exc.reason or "").lower()
            if "pairing" in reason:
                self._set_state(GatewayState.PAIRING_REQUIRED)
            elif "auth" in reason:
                self._set_state(GatewayState.AUTH_REQUIRED)
            else:
                self._set_state(GatewayState.UNREACHABLE)
        except Exception:  # pragma: no cover
            log.exception("reader loop crashed")
            self._set_state(GatewayState.ERROR)
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(GatewayError("Connection lost"))
            self._pending.clear()

    def _dispatch(self, msg: dict[str, Any]) -> None:
        typ = msg.get("type")
        if typ == "res":
            fut = self._pending.pop(msg.get("id", ""), None)
            if fut and not fut.done():
                if msg.get("error"):
                    err = msg["error"]
                    fut.set_exception(
                        RpcError(
                            method=msg.get("method", "?"),
                            code=err.get("code"),
                            message=err.get("message", "Unknown error"),
                        )
                    )
                else:
                    fut.set_result(msg.get("result"))
        elif typ == "event":
            # OpenClaw emits events for streaming replies, tokens, etc.
            # Hook into these via subclassing / callbacks later.
            log.debug("event: %s", msg.get("name"))
        else:
            log.debug("unknown frame type %r", typ)

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    async def _auth_handshake(self) -> None:
        """Send the `connect` request with auth fields."""
        params: dict[str, Any] = {
            "auth": {},
            "client": "clawdeck",
            "label": self.device_label,
        }
        if self.token:
            params["auth"]["token"] = self.token
        if self.password:
            params["auth"]["password"] = self.password

        try:
            await self.call("connect", params, timeout=10.0)
        except RpcError as exc:
            msg = (exc.message or "").lower()
            if "pairing" in msg:
                raise PairingRequiredError(exc.message) from exc
            if "auth" in msg or "password" in msg or "unauthorized" in msg:
                raise AuthError(exc.message) from exc
            raise

    async def send_message(self, text: str, *, timeout: float = 120.0) -> str:
        """Send a prompt to the agent and return the reply text."""
        result = await self.call(
            "agent.run",
            {"message": text, "stream": False},
            timeout=timeout,
        )
        if isinstance(result, dict):
            # Expected shape: { payloads: [ { text, ... } ], meta: {...} }
            payloads = result.get("payloads") or []
            if payloads and isinstance(payloads, list):
                return str(payloads[0].get("text", ""))
            return str(result.get("text", ""))
        return str(result)

    async def list_pending_devices(self) -> list[PendingDevice]:
        res = await self.call("devices.list")
        pending: list[PendingDevice] = []
        for row in (res or {}).get("pending", []):
            pending.append(
                PendingDevice(
                    request_id=row.get("requestId", row.get("id", "")),
                    device_id=row.get("deviceId", ""),
                    role=row.get("role", ""),
                    scopes=row.get("scopes", []),
                    ip=row.get("ip"),
                    flags=row.get("flags", []),
                )
            )
        return pending

    async def approve_device(self, request_id: str) -> None:
        await self.call("devices.approve", {"requestId": request_id})

"""Cost / usage aggregator.

OpenClaw exposes a ``gateway.usage-cost`` CLI subcommand and an underlying RPC
that reports per-provider token and dollar totals. We shell out to it via
``VBoxManage guestcontrol`` because Phase 1 doesn't require a persistent WS
connection for this data.

Falls back to parsing ``openclaw infer model providers`` JSON output when the
``usage-cost`` subcommand is unavailable.

Data model mirrors what the OpenClaw CLI emits:

    {
      "since": "2026-04-12T00:00:00Z",
      "until": "2026-04-19T00:00:00Z",
      "totals": { "input": 1234, "output": 5678, "usd": 0.12 },
      "byProvider": [
          {"provider": "scitely", "model": "qwen3-max",
           "input": 1234, "output": 5678, "usd": 0.12, "calls": 42}
      ],
      "byDay": [
          {"day": "2026-04-19", "input": 100, "output": 200, "usd": 0.01}
      ]
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from .vm import VmController, VmError

log = logging.getLogger(__name__)


@dataclass
class UsageTotals:
    input: int = 0
    output: int = 0
    usd: float = 0.0


@dataclass
class ProviderUsage:
    provider: str
    model: str | None
    input: int = 0
    output: int = 0
    usd: float = 0.0
    calls: int = 0


@dataclass
class DayUsage:
    day: str         # YYYY-MM-DD
    input: int = 0
    output: int = 0
    usd: float = 0.0


@dataclass
class UsageSnapshot:
    since: datetime | None = None
    until: datetime | None = None
    totals: UsageTotals = field(default_factory=UsageTotals)
    by_provider: list[ProviderUsage] = field(default_factory=list)
    by_day: list[DayUsage] = field(default_factory=list)


class UsageAggregator:
    """Fetches usage from the OpenClaw CLI inside the VM."""

    def __init__(self, vm: VmController):
        self.vm = vm

    async def snapshot(self, days: int = 7) -> UsageSnapshot:
        """Return a snapshot covering the last ``days`` days.

        Never raises — returns an empty snapshot on any failure so the UI can
        just render zeros.
        """
        try:
            raw = await self.vm.guest_exec(
                f"openclaw gateway usage-cost --since {days}d --json 2>/dev/null "
                "|| echo '{}'",
                timeout=30.0, allow_fail=True,
            )
        except VmError as exc:
            log.debug("usage-cost fetch failed: %s", exc)
            return UsageSnapshot()

        try:
            data = json.loads(raw or "{}")
        except ValueError:
            log.debug("usage-cost returned non-JSON: %s", (raw or "")[:200])
            return UsageSnapshot()

        return _parse(data)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse(data: dict) -> UsageSnapshot:
    snap = UsageSnapshot()
    snap.since = _dt(data.get("since"))
    snap.until = _dt(data.get("until"))

    totals = data.get("totals") or {}
    snap.totals = UsageTotals(
        input=int(totals.get("input", 0)),
        output=int(totals.get("output", 0)),
        usd=float(totals.get("usd", 0.0)),
    )

    for row in data.get("byProvider", []) or []:
        snap.by_provider.append(
            ProviderUsage(
                provider=str(row.get("provider", "unknown")),
                model=row.get("model"),
                input=int(row.get("input", 0)),
                output=int(row.get("output", 0)),
                usd=float(row.get("usd", 0.0)),
                calls=int(row.get("calls", 0)),
            )
        )

    for row in data.get("byDay", []) or []:
        snap.by_day.append(
            DayUsage(
                day=str(row.get("day", "")),
                input=int(row.get("input", 0)),
                output=int(row.get("output", 0)),
                usd=float(row.get("usd", 0.0)),
            )
        )

    return snap


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None

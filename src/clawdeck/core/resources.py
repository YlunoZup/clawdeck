"""Resource monitor — CPU, RAM, uptime inside the VM.

Shells out once via ``VBoxManage guestcontrol`` to read ``/proc/stat``,
``/proc/meminfo`` and ``/proc/uptime``. Each snapshot is cheap (~50-100ms);
the monitor loop drives polling cadence.

CPU usage is computed differentially — the first sample returns 0% and each
subsequent sample compares against the previous counters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from .vm import VmController, VmError

log = logging.getLogger(__name__)


@dataclass
class ResourceSample:
    when: datetime
    cpu_percent: float         # 0.0 — 100.0
    mem_used_mb: float
    mem_total_mb: float
    uptime: timedelta | None = None

    @property
    def mem_percent(self) -> float:
        if self.mem_total_mb <= 0:
            return 0.0
        return 100.0 * self.mem_used_mb / self.mem_total_mb


class ResourceMonitor:
    def __init__(self, vm: VmController, history_size: int = 60):
        self.vm = vm
        self._history_size = history_size
        self._history: list[ResourceSample] = []
        self._last_cpu: tuple[int, int] | None = None  # (idle, total)

    @property
    def history(self) -> list[ResourceSample]:
        return list(self._history)

    # ------------------------------------------------------------------

    async def sample(self) -> ResourceSample | None:
        script = (
            "head -n1 /proc/stat && echo '---' && "
            "head -n3 /proc/meminfo && echo '---' && "
            "cat /proc/uptime"
        )
        try:
            out = await self.vm.guest_exec(script, timeout=10.0, allow_fail=True)
        except VmError as exc:
            log.debug("resource sample failed: %s", exc)
            return None

        parts = (out or "").split("---")
        if len(parts) < 3:
            return None

        cpu_pct = self._parse_cpu(parts[0])
        mem_used, mem_total = self._parse_mem(parts[1])
        uptime = self._parse_uptime(parts[2])

        s = ResourceSample(
            when=datetime.now(),
            cpu_percent=cpu_pct,
            mem_used_mb=mem_used,
            mem_total_mb=mem_total,
            uptime=uptime,
        )
        self._history.append(s)
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]
        return s

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_cpu(self, raw: str) -> float:
        """Parse the first ``cpu`` line of /proc/stat into a %-used number."""
        line = (raw or "").strip().splitlines()
        if not line:
            return 0.0
        tokens = line[0].split()
        if tokens and tokens[0] == "cpu":
            tokens = tokens[1:]
        try:
            nums = [int(t) for t in tokens[:7]]
        except ValueError:
            return 0.0
        # user nice system idle iowait irq softirq
        total = sum(nums)
        idle = nums[3] if len(nums) > 3 else 0

        if self._last_cpu is None:
            self._last_cpu = (idle, total)
            return 0.0

        prev_idle, prev_total = self._last_cpu
        delta_total = total - prev_total
        delta_idle = idle - prev_idle
        self._last_cpu = (idle, total)

        if delta_total <= 0:
            return 0.0
        return max(0.0, 100.0 * (1.0 - delta_idle / delta_total))

    def _parse_mem(self, raw: str) -> tuple[float, float]:
        """Parse /proc/meminfo top lines. Returns (used_mb, total_mb)."""
        total_kb = 0
        avail_kb = 0
        for line in (raw or "").splitlines():
            if line.startswith("MemTotal:"):
                total_kb = _kb_from_line(line)
            elif line.startswith("MemAvailable:"):
                avail_kb = _kb_from_line(line)
        total_mb = total_kb / 1024.0
        used_mb = (total_kb - avail_kb) / 1024.0 if total_kb else 0.0
        return used_mb, total_mb

    def _parse_uptime(self, raw: str) -> timedelta | None:
        s = (raw or "").strip().split()
        if not s:
            return None
        try:
            seconds = float(s[0])
        except ValueError:
            return None
        return timedelta(seconds=seconds)


def _kb_from_line(line: str) -> int:
    """/proc/meminfo lines look like `MemTotal:     8000000 kB`."""
    parts = line.split()
    try:
        return int(parts[1])
    except (ValueError, IndexError):
        return 0

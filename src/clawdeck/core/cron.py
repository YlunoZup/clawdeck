"""Wrapper around ``openclaw cron`` for scheduled jobs.

All commands shell out inside the guest VM. The controller is stateless — the
UI re-queries for every render so a manually-added cron job (via CLI inside
the VM) shows up immediately.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .vm import VmController, VmError

log = logging.getLogger(__name__)


@dataclass
class CronJob:
    id: str
    schedule: str        # cron expression
    command: str
    enabled: bool
    next_run: str | None = None
    last_run: str | None = None
    description: str = ""


class CronController:
    def __init__(self, vm: VmController):
        self.vm = vm

    async def list(self) -> list[CronJob]:
        try:
            raw = await self.vm.guest_exec(
                "openclaw cron list --json 2>/dev/null || echo '[]'",
                allow_fail=True, timeout=15.0,
            )
        except VmError as exc:
            log.debug("cron list failed: %s", exc)
            return []

        try:
            data = json.loads(raw or "[]")
        except ValueError:
            log.debug("cron list returned non-JSON: %s", (raw or "")[:200])
            return []

        out: list[CronJob] = []
        for row in data:
            out.append(
                CronJob(
                    id=str(row.get("id", "")),
                    schedule=str(row.get("schedule", "")),
                    command=str(row.get("command", "")),
                    enabled=bool(row.get("enabled", True)),
                    next_run=row.get("nextRun"),
                    last_run=row.get("lastRun"),
                    description=str(row.get("description", "")),
                )
            )
        return out

    async def add(
        self,
        *,
        schedule: str,
        command: str,
        description: str = "",
    ) -> bool:
        desc_arg = f' --description "{_shell_escape(description)}"' if description else ""
        cmd = (
            f'openclaw cron add --schedule "{_shell_escape(schedule)}" '
            f'--command "{_shell_escape(command)}"{desc_arg}'
        )
        try:
            await self.vm.guest_exec(cmd, allow_fail=True, timeout=15.0)
            return True
        except VmError as exc:
            log.warning("cron add failed: %s", exc)
            return False

    async def remove(self, job_id: str) -> bool:
        try:
            await self.vm.guest_exec(
                f'openclaw cron remove "{_shell_escape(job_id)}"',
                allow_fail=True, timeout=15.0,
            )
            return True
        except VmError as exc:
            log.warning("cron remove failed: %s", exc)
            return False

    async def set_enabled(self, job_id: str, enabled: bool) -> bool:
        verb = "enable" if enabled else "disable"
        try:
            await self.vm.guest_exec(
                f'openclaw cron {verb} "{_shell_escape(job_id)}"',
                allow_fail=True, timeout=15.0,
            )
            return True
        except VmError as exc:
            log.warning("cron %s failed: %s", verb, exc)
            return False


def _shell_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')

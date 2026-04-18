"""VirtualBox VM controller.

Thin async wrapper around ``VBoxManage``. Every subprocess call runs off-thread so
the UI event loop never blocks.

Contract:
- ``VmController`` is stateless — always queries VBoxManage. No caching here.
  The monitor loop owns polling cadence.
- Errors surface as ``VmError`` subclasses, never raw ``CalledProcessError``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..models import VmState
from ..utils.platform import find_vboxmanage, is_windows

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class VmError(Exception):
    """Base class for VM controller errors."""


class VBoxManageMissingError(VmError):
    """VBoxManage executable couldn't be located."""


class VmNotFoundError(VmError):
    """The configured VM name doesn't exist in VirtualBox."""


class VmCommandError(VmError):
    """VBoxManage returned non-zero."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"VBoxManage failed ({returncode}): {' '.join(cmd)}\n{stderr}"
        )


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VmInfo:
    name: str
    uuid: str
    state: VmState
    ip: str | None = None


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class VmController:
    """Async VirtualBox controller.

    Parameters
    ----------
    vm_name:
        The VM's VirtualBox display name, e.g. ``OpenClaw``.
    vboxmanage_path:
        Optional explicit path; auto-detected when ``None``.
    guest_user / guest_password:
        Credentials used for ``VBoxManage guestcontrol ... run``. Optional — only
        required if you actually run guest commands.
    """

    def __init__(
        self,
        vm_name: str,
        vboxmanage_path: Path | None = None,
        guest_user: str | None = None,
        guest_password: str | None = None,
    ):
        self.vm_name = vm_name
        self._vboxmanage = vboxmanage_path or find_vboxmanage()
        self.guest_user = guest_user
        self.guest_password = guest_password

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_vboxmanage(self) -> Path:
        if self._vboxmanage is None or not self._vboxmanage.exists():
            raise VBoxManageMissingError(
                "VBoxManage not found. Install VirtualBox or set "
                "`vm.vboxmanage_path` in config."
            )
        return self._vboxmanage

    async def _run(
        self,
        *args: str,
        timeout: float = 30.0,
        check: bool = True,
    ) -> tuple[int, str, str]:
        exe = self._require_vboxmanage()
        cmd = [str(exe), *args]
        log.debug("VBoxManage: %s", " ".join(cmd))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Hide console windows on Windows when launched from a GUI
            creationflags=(
                subprocess.CREATE_NO_WINDOW if is_windows() else 0
            ),
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError as exc:
            proc.kill()
            raise VmCommandError(cmd, -1, f"Timeout after {timeout}s") from exc

        stdout = out.decode(errors="replace").strip()
        stderr = err.decode(errors="replace").strip()

        if check and proc.returncode != 0:
            raise VmCommandError(cmd, proc.returncode or -1, stderr or stdout)
        return proc.returncode or 0, stdout, stderr

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------

    async def exists(self) -> bool:
        _, out, _ = await self._run("list", "vms", check=False)
        return f'"{self.vm_name}"' in out

    async def info(self) -> VmInfo:
        """Parse the machine-readable info block."""
        if not await self.exists():
            raise VmNotFoundError(f"VM {self.vm_name!r} not registered")

        _, out, _ = await self._run(
            "showvminfo", self.vm_name, "--machinereadable"
        )

        fields: dict[str, str] = {}
        for line in out.splitlines():
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            # Strip surrounding quotes VBoxManage uses
            fields[k.strip()] = v.strip().strip('"')

        return VmInfo(
            name=fields.get("name", self.vm_name),
            uuid=fields.get("UUID", ""),
            state=VmState.from_vbox(fields.get("VMState", "")),
            ip=fields.get("GuestIPAddress"),
        )

    async def state(self) -> VmState:
        try:
            info = await self.info()
            return info.state
        except VmNotFoundError:
            return VmState.UNKNOWN
        except VmError as exc:
            log.warning("state() error: %s", exc)
            return VmState.UNKNOWN

    async def start(self, headless: bool = True) -> None:
        """Start the VM if it's not already running."""
        current = await self.state()
        if current == VmState.RUNNING:
            log.info("VM %s already running", self.vm_name)
            return
        log.info("Starting VM %s (headless=%s)", self.vm_name, headless)
        await self._run(
            "startvm",
            self.vm_name,
            "--type", "headless" if headless else "gui",
            timeout=120.0,
        )

    async def stop(self, graceful: bool = True) -> None:
        """Power off the VM. ``graceful=True`` uses ACPI shutdown first."""
        if graceful:
            # Best-effort ACPI
            try:
                await self._run(
                    "controlvm", self.vm_name, "acpipowerbutton",
                    timeout=10.0, check=False,
                )
                # Allow some time for graceful shutdown
                for _ in range(20):  # ~20s
                    await asyncio.sleep(1)
                    if await self.state() != VmState.RUNNING:
                        return
            except VmError:
                pass  # fall through to hard power off
        log.info("Power-off VM %s", self.vm_name)
        await self._run("controlvm", self.vm_name, "poweroff", check=False)

    async def pause(self) -> None:
        await self._run("controlvm", self.vm_name, "pause", check=False)

    async def resume(self) -> None:
        await self._run("controlvm", self.vm_name, "resume", check=False)

    async def ensure_running(self, headless: bool = True) -> None:
        """Start if not running; resume if paused."""
        s = await self.state()
        if s == VmState.RUNNING:
            return
        if s == VmState.PAUSED:
            await self.resume()
            return
        await self.start(headless=headless)

    async def add_port_forward(
        self,
        rule_name: str,
        host_port: int,
        guest_port: int,
        protocol: str = "tcp",
        nic: int = 1,
    ) -> None:
        """Add a NAT port forward (live, no VM restart)."""
        await self._run(
            "controlvm", self.vm_name, f"natpf{nic}",
            f"{rule_name},{protocol},,{host_port},,{guest_port}",
            check=False,
        )

    # ------------------------------------------------------------------
    # Guest execution
    # ------------------------------------------------------------------

    async def guest_exec(
        self,
        command: str,
        *,
        timeout: float = 60.0,
        allow_fail: bool = False,
    ) -> str:
        """Run a shell command inside the guest via VBoxManage guestcontrol.

        Requires guest_user + guest_password to be configured.
        Returns stdout of the guest command.
        """
        if not (self.guest_user and self.guest_password):
            raise VmError("Guest credentials not configured")

        # MSYS/Git-Bash on Windows rewrites /usr/bin/bash → Windows paths.
        # We side-step by passing the `-c <script>` arg structure unchanged.
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"

        exe = self._require_vboxmanage()
        cmd = [
            str(exe),
            "guestcontrol",
            self.vm_name,
            "run",
            "--exe", "/usr/bin/bash",
            "--username", self.guest_user,
            "--password", self.guest_password,
            "--", "-c", command,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if is_windows() else 0
            ),
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except TimeoutError as exc:
            proc.kill()
            raise VmCommandError(
                cmd, -1, f"guest_exec timeout after {timeout}s"
            ) from exc

        stdout = out.decode(errors="replace")
        stderr = err.decode(errors="replace")
        code = proc.returncode or 0

        # VBoxManage returns 18 when grep-style commands have no matches.
        # We tolerate these when the caller allows failure.
        if code != 0 and not allow_fail:
            raise VmCommandError(cmd, code, stderr)

        return stdout.rstrip("\r\n")

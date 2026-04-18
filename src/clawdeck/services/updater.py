"""Auto-update checker.

Polls GitHub Releases for the repo slug configured in ``pyproject``
(``YlunoZup/clawdeck``) and exposes the latest release metadata for the UI to
render an "update available" banner.

We deliberately do **not** auto-download. The user clicks the link and picks
up the new ``clawdeck.exe`` themselves. This keeps us out of
"rogue auto-update ate my data" territory and avoids needing code signing for
silent replacement.

An update-check is a single HTTPS GET, <1 KB response, fully rate-limit-safe
(unauthenticated GitHub API is 60/hour per IP).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from .. import __version__

log = logging.getLogger(__name__)

DEFAULT_REPO = "YlunoZup/clawdeck"
USER_AGENT = f"ClawDeck/{__version__}"


@dataclass
class Release:
    tag: str                   # "v0.3.0"
    name: str
    url: str                   # html_url for the release
    published_at: datetime | None
    body: str                  # release notes
    asset_urls: dict[str, str] # filename -> download URL


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------


def parse_semver(s: str) -> tuple[int, int, int] | None:
    """Parse "v0.3.0" / "0.3.0" / "0.3.0-alpha.1" → (0, 3, 0). None if invalid."""
    s = (s or "").lstrip("vV").split("+", 1)[0].split("-", 1)[0]
    parts = s.split(".")
    if len(parts) < 2:
        return None
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) >= 3 else 0
    except ValueError:
        return None
    return (major, minor, patch)


def is_newer(remote_tag: str, local_version: str) -> bool:
    remote = parse_semver(remote_tag)
    local = parse_semver(local_version)
    if remote is None or local is None:
        return False
    return remote > local


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------


class UpdateChecker:
    def __init__(
        self,
        repo: str = DEFAULT_REPO,
        current_version: str = __version__,
    ):
        self.repo = repo
        self.current_version = current_version
        self._last_check: datetime | None = None
        self._last_result: Release | None = None

    async def fetch_latest(self, timeout: float = 6.0) -> Release | None:
        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            ) as c:
                r = await c.get(url)
        except httpx.HTTPError as exc:
            log.debug("update check failed: %s", exc)
            return None

        if r.status_code != 200:
            log.debug("update check returned %s: %s", r.status_code, r.text[:120])
            return None

        try:
            release = _parse(r.json())
        except (ValueError, KeyError) as exc:
            log.debug("update check parse failed: %s", exc)
            return None

        self._last_check = datetime.now()
        self._last_result = release
        return release

    async def has_update(self) -> Release | None:
        """Fetch + compare. Returns the release if it's newer, else None."""
        rel = await self.fetch_latest()
        if rel and is_newer(rel.tag, self.current_version):
            return rel
        return None


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _parse(data: dict[str, Any]) -> Release:
    assets = data.get("assets") or []
    asset_urls = {
        str(a.get("name", "")): str(a.get("browser_download_url", ""))
        for a in assets
        if a.get("name") and a.get("browser_download_url")
    }

    published = data.get("published_at")
    try:
        pub_dt = datetime.fromisoformat(
            published.replace("Z", "+00:00")
        ) if isinstance(published, str) else None
    except ValueError:
        pub_dt = None

    return Release(
        tag=str(data["tag_name"]),
        name=str(data.get("name") or data["tag_name"]),
        url=str(data.get("html_url", "")),
        published_at=pub_dt,
        body=str(data.get("body", "")),
        asset_urls=asset_urls,
    )

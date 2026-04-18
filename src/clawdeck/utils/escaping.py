"""String-escaping helpers shared across modules.

Kept in one place so XML / shell / AppleScript escaping rules don't silently
drift between notification builders, autostart plist writers, and guest-exec
command formatters.
"""

from __future__ import annotations

import shlex


def xml_escape(s: str) -> str:
    """Safe-for-XML attribute *and* element text."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&apos;")
        .replace('"', "&quot;")
    )


def shell_quote_posix(s: str) -> str:
    """POSIX single-quote escape for a value pasted into a shell string."""
    return shlex.quote(s)


def osa_escape(s: str) -> str:
    """AppleScript string literal escape."""
    return s.replace("\\", "\\\\").replace('"', '\\"')

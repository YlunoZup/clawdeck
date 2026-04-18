"""Tunnel URL regex + state assignment tests."""

from __future__ import annotations

import re

from clawdeck.core.tunnel import URL_RE


def test_url_regex_accepts_quick_tunnel():
    m = URL_RE.search("your url is: https://rpg-wizard-can-pace.trycloudflare.com")
    assert m is not None
    assert m.group(0) == "https://rpg-wizard-can-pace.trycloudflare.com"


def test_url_regex_rejects_random_https():
    m = URL_RE.fullmatch("https://example.com")
    assert m is None


def test_url_regex_picks_latest():
    log = """
    2026-04-15T20:44:32Z INF ... https://older-subdomain.trycloudflare.com
    2026-04-16T00:12:25Z INF ... https://desert-envelope-washer-uses.trycloudflare.com
    2026-04-17T03:50:00Z INF ... https://rpg-wizard-can-pace.trycloudflare.com
    """
    urls = URL_RE.findall(log)
    assert urls[-1] == "https://rpg-wizard-can-pace.trycloudflare.com"

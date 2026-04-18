"""Resource monitor parser tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from clawdeck.core.resources import ResourceMonitor


def _mon() -> ResourceMonitor:
    return ResourceMonitor(MagicMock())


def test_parse_mem_basic():
    mon = _mon()
    text = (
        "MemTotal:     8000000 kB\n"
        "MemFree:      2000000 kB\n"
        "MemAvailable: 6000000 kB\n"
    )
    used, total = mon._parse_mem(text)
    # total = 8,000,000 kB → 7812.5 MB
    assert round(total, 1) == 7812.5
    # used = total - available = 2,000,000 kB → 1953.125 MB
    assert round(used, 1) == 1953.1


def test_parse_cpu_diff():
    mon = _mon()
    # First sample establishes baseline → 0%
    first = mon._parse_cpu("cpu 100 0 100 800 0 0 0")
    assert first == 0.0
    # Second sample: deltas user=+20 nice=0 system=+20 idle=+80 → total=+120, idle=+80
    # busy = 1 - 80/120 = 33.3%
    second = mon._parse_cpu("cpu 120 0 120 880 0 0 0")
    assert 32.0 <= second <= 35.0


def test_parse_uptime():
    mon = _mon()
    up = mon._parse_uptime("1234.56 789.01")
    assert up is not None
    assert up.total_seconds() == 1234.56


def test_sample_percent_clamps():
    mon = _mon()
    # Identical consecutive samples → 0%
    mon._parse_cpu("cpu 100 0 100 100 0 0 0")
    assert mon._parse_cpu("cpu 100 0 100 100 0 0 0") == 0.0

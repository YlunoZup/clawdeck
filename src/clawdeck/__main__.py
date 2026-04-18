"""Module entry point for ``python -m clawdeck``."""

from __future__ import annotations

import sys

from clawdeck.cli import main

if __name__ == "__main__":
    sys.exit(main())

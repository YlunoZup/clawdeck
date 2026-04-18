"""Quick dev launcher: `python scripts/dev.py` runs clawdeck from source."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from clawdeck.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

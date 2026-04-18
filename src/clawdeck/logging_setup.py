"""Centralized logging configuration.

Rotates logs at 5 MB × 5 files under the platform log dir.
Also logs to stderr during development.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from .utils.paths import log_dir

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure(level: int = logging.INFO, also_stderr: bool = True) -> Path:
    """Install root handlers. Returns the log-file path."""
    log_file = log_dir() / "clawdeck.log"

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing handlers (e.g. PyInstaller sets its own)
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(DEFAULT_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if also_stderr:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    # Quiet overly chatty deps
    for noisy in ("websockets.client", "httpx", "keyring"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return log_file

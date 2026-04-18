"""Path helpers for ClawDeck config, logs, data directories.

Uses `platformdirs` so paths follow each OS's conventions:
- Windows:  %APPDATA%/ClawDeck
- macOS:    ~/Library/Application Support/ClawDeck
- Linux:    ~/.config/clawdeck
"""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir, user_data_dir, user_log_dir

APP_NAME = "ClawDeck"
APP_AUTHOR = False  # don't nest under an author dir


def config_dir() -> Path:
    p = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_dir() -> Path:
    p = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    p.mkdir(parents=True, exist_ok=True)
    return p


def log_dir() -> Path:
    p = Path(user_log_dir(APP_NAME, APP_AUTHOR))
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_file() -> Path:
    return config_dir() / "config.toml"


def chat_history_dir() -> Path:
    p = data_dir() / "chats"
    p.mkdir(parents=True, exist_ok=True)
    return p

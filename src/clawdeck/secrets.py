"""Secret storage via the OS credential store.

Backed by `keyring`, which maps to:
- Windows: Windows Credential Manager
- macOS:   Keychain
- Linux:   Secret Service (GNOME Keyring / KDE KWallet)

All secrets are stored under a single service name so uninstallers can wipe them
with one call. No secret ever touches disk in plain form.
"""

from __future__ import annotations

import logging

import keyring
from keyring.errors import KeyringError

log = logging.getLogger(__name__)

SERVICE = "ClawDeck"

# Known keys — declared as constants so typos get caught at review time.
GATEWAY_PASSWORD = "gateway.password"
GATEWAY_TOKEN = "gateway.token"
VM_USER_PASSWORD = "vm.user.password"     # for VBoxManage guestcontrol


def set_secret(key: str, value: str) -> None:
    try:
        keyring.set_password(SERVICE, key, value)
        log.debug("Stored secret %s", key)
    except KeyringError as exc:
        log.error("Failed to store secret %s: %s", key, exc)
        raise


def get_secret(key: str) -> str | None:
    try:
        return keyring.get_password(SERVICE, key)
    except KeyringError as exc:
        log.error("Failed to read secret %s: %s", key, exc)
        return None


def delete_secret(key: str) -> None:
    try:
        keyring.delete_password(SERVICE, key)
    except keyring.errors.PasswordDeleteError:
        pass  # already gone → idempotent
    except KeyringError as exc:
        log.error("Failed to delete secret %s: %s", key, exc)


def wipe_all() -> None:
    """Remove every known secret. Called from the uninstaller."""
    for k in (GATEWAY_PASSWORD, GATEWAY_TOKEN, VM_USER_PASSWORD):
        delete_secret(k)

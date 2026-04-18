# Changelog

All notable changes to ClawDeck will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
project adheres to [SemVer](https://semver.org/).

## [Unreleased] — Phase 2

### Added
- **SQLite chat history** — persistent sessions at `%APPDATA%/ClawDeck/chats.db`
  with session switcher in the Chat tab (new/delete/switch)
- **Windows toast notifications** — native WinRT toasts on gateway up/down,
  tunnel URL rotation, and unhealthy-state transitions (no spam; only fires
  on state changes)
- **QR code for mobile tunnel URL** — Home tab has a "Show QR for phone"
  toggle that renders the current `trycloudflare.com` URL as a QR image.
  Auto-refreshes when the URL rotates
- **Log viewer filters + search** — level dropdown (ALL/DEBUG/INFO/WARN/ERROR),
  text search box, auto-follow toggle, copy-visible button
- **Multiple profiles scaffolding** — `ProfileStore` + templates for local,
  VPS, and Tailscale peer; UI switcher in Phase 3
- **Usage / cost tab** — totals + per-provider + per-day breakdown, sourced
  from `openclaw gateway usage-cost --json`
- **Cron tab** — list/add/remove/toggle scheduled jobs, wrapping
  `openclaw cron` inside the VM
- **Auto-sync allowed origins** — when the tunnel URL rotates, ClawDeck
  pushes the new URL into `gateway.controlUi.allowedOrigins` on the VM and
  restarts the gateway via systemd (removes the "origin not allowed" footgun)
- **First-run wizard** — modal dialog on first launch; collects VM name,
  guest credentials, gateway info, and seeds the config + keychain

### Internal
- `StateHub` in `cli.py` fans state changes to tray/window/notify/sync
- `on_attach` lifecycle hook on tabs that need lazy refresh (Usage, Cron, Chat)
- 36 unit tests across all new modules

## [Unreleased] — Phase 1 MVP

### Added
- Initial project scaffolding with `src/` layout
- `clawdeck.models` — shared state dataclasses + enums
- `clawdeck.config` — TOML load/save with schema validation + broken-file backup
- `clawdeck.secrets` — keyring wrapper (Windows Credential Manager)
- `clawdeck.logging_setup` — rotating file + stderr handler
- `clawdeck.core.vm` — async VBoxManage controller (start/stop/pause/resume,
  guest_exec for in-VM commands)
- `clawdeck.core.gateway` — OpenClaw WebSocket client with HTTP health probe
  fallback to raw TCP, surfaces auth/pairing errors cleanly
- `clawdeck.core.tunnel` — Cloudflare quick-tunnel URL watcher + reachability
- `clawdeck.core.monitor` — background poller with change notifications
- `clawdeck.services.autostart` — HKCU Run-key integration + legacy task
  migration
- `clawdeck.ui.icons` — PIL-generated coloured status icons (no asset files)
- `clawdeck.ui.tray` — pystray tray with menu + live status
- `clawdeck.ui.window` — Flet tabbed main window
- Views: Home (status + quick actions), Chat (agent inline), Logs (tail),
  Settings (config + secrets)
- Absolute-import `clawdeck.cli:main` entrypoint (PyInstaller-safe)
- `scripts/build.py` — one-file .exe builder
- `scripts/install_windows.ps1` + `uninstall_windows.ps1`
- GitHub Actions CI (Windows + Ubuntu, Python 3.11/3.12/3.13)
- Unit tests for config, models, icons, tunnel regex, gateway, autostart
- MIT licence, README, ARCHITECTURE, SETUP, DEVELOPMENT, FEATURES docs

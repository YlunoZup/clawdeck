# Changelog

All notable changes to ClawDeck will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
project adheres to [SemVer](https://semver.org/).

## [0.3.0] — Phase 3

### Added
- **Plugin system** (`services/plugins.py`) — drop `.py` files into
  `~/.clawdeck/plugins/`, subclass `BasePlugin`, get startup/state/shutdown
  hooks. Faulty plugins are quarantined, never crash the host
- **Auto-update checker** (`services/updater.py`) — polls GitHub Releases;
  banner in the main window when a newer tag ships
- **Tailscale integration** (`core/tailscale.py`, new *Tailscale* tab) —
  detects the local `tailscale` CLI, lists peers, surfaces exit-node state,
  one-click set/clear exit node
- **Resource monitor** (`core/resources.py`, `ui/components/sparkline.py`) —
  CPU/RAM/uptime sampling from `/proc/stat` and `/proc/meminfo` via
  guestcontrol, ready for Home-tab sparklines
- **Remote federation** (`federation.py`) — data model for multiple reachable
  gateways with active-profile switching
- **Profile switcher** — dropdown in the top bar; persists selection
- **Cross-platform autostart** — macOS LaunchAgent + Linux XDG `.desktop`
  alongside the existing Windows HKCU Run key
- **Cross-platform CI** — GitHub Actions matrix now covers Windows, Linux,
  and macOS for Python 3.11/3.12/3.13
- **Release workflow** (`.github/workflows/release.yml`) — builds signed-in-
  spirit binaries for all three platforms on every `v*` tag push

### Security
- Shell metacharacters in the tunnel URL and guest password are now
  `shlex.quote`-ed before being interpolated into `guest_exec` scripts
- Duplicate XML / OSA escape helpers consolidated into `utils/escaping.py`

### Internal
- 60 unit tests across every new module
- `Usage` tab now cancels stale refresh tasks when the user clicks Refresh
  again, avoiding parallel `guest_exec` pileups

## [0.2.0] — Phase 2

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

## [0.1.0] — Phase 1 MVP

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

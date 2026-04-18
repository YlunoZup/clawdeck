# ClawDeck — Features

## Phase 1 (this release)

| Area | Feature | Notes |
|------|---------|-------|
| **Tray** | Live status icon | Green = healthy, yellow = starting/tunnel down, red = error, grey = offline |
| | Right-click menu | Open app, open dashboard, start/stop VM, copy tunnel URL, quit |
| | Hide-to-tray on `×` | Window closes to tray, app keeps running |
| **Window** | Home tab | VM/gateway/tunnel status cards, tunnel URL, quick actions |
| | Chat tab | Native prompt → reply with your OpenClaw agent |
| | Logs tab | Live tail of `clawdeck.log` |
| | Settings tab | Edit every config field + secrets |
| | Auto theme | Follows Windows light/dark preference |
| **VM** | VirtualBox support | Start, stop (graceful + force), pause, resume, port forward |
| | Auto-start on launch | Ensures VM running when ClawDeck starts |
| | Headless mode | Configurable |
| **Gateway** | WebSocket client | Auto-connects with password + token |
| | Health monitoring | 5s HTTP probe |
| | Chat API | `agent.run` RPC with streaming-off mode |
| | Device pairing | List + approve from the UI |
| **Tunnel** | Cloudflare quick-tunnel detection | Reads guest log for newest `*.trycloudflare.com` URL |
| | Auto-rotation handling | Picks up new URL when the tunnel restarts |
| | Reachability probe | HTTPS HEAD check every 30s |
| **Secrets** | OS keychain storage | Windows Credential Manager |
| | Wipe on uninstall | `-Purge` flag clears all secrets |
| **Lifecycle** | Windows autostart | HKCU Run key (no admin needed) |
| | Legacy task cleanup | Removes old `OpenClaw-AutoStart` scheduled task |
| **Build** | One-file `clawdeck.exe` | PyInstaller; no Python install required |
| | Installer + uninstaller | PowerShell scripts |

## Phase 2 (shipped)

| Area | Feature | Notes |
|------|---------|-------|
| **Chat** | SQLite history | `%APPDATA%/ClawDeck/chats.db`; sessions persist across restarts |
| | Session switcher | Dropdown with last-50 sessions, new/delete buttons |
| **Notifications** | Windows toasts | WinRT native; fires on gateway on/off, tunnel up/down, URL rotation, red health |
| **Mobile** | QR code for tunnel URL | One tap on Home → scan with phone → open dashboard anywhere |
| **Logs** | Level filter | ALL / DEBUG / INFO / WARNING / ERROR dropdown |
| | Search box | Case-insensitive substring filter |
| | Auto-follow toggle + copy-visible | So you can pause a rush of logs to inspect |
| **Profiles** | Multi-profile scaffold | `ProfileStore` with local / VPS / Tailscale templates |
| **Usage** | Cost tracker tab | Totals + per-provider + per-day sourced from `openclaw gateway usage-cost --json` |
| **Cron** | Scheduled jobs UI | Add / remove / enable / disable; wraps `openclaw cron` |
| **Lifecycle** | Auto-sync allowed origins | Tunnel rotation → new origin pushed to gateway + systemd restart |
| | First-run wizard | Modal dialog on first launch collects VM + gateway credentials |

## Phase 2 — planned but deferred

- Embedded dashboard webview (waiting on Flet webview stability)
- Resource graphs (CPU/RAM inside the VM)

## Phase 3 (vision)

- macOS + Linux builds
- Tailscale exit-node wiring out of the box
- Plugin system: drop a Python module in `plugins/` and it shows up
- Remote control: one ClawDeck manages multiple OpenClaw stacks
- Built-in backup manager for `~/.openclaw`

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the technical design.

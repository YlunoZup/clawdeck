# ClawDeck — Architecture

## Goal

A personal desktop control panel for [OpenClaw](https://openclaw.ai) agents. Manages
the full stack on a user's laptop: VirtualBox VM lifecycle, gateway process, public
tunnel, chat interface, and monitoring. Auto-starts with the OS, lives in the system
tray, opens a rich UI on demand.

Designed to be **open source**, **cross-platform** (Windows first, macOS/Linux next),
and **low-friction** — install once, never configure again.

## Non-goals

- Not a replacement for OpenClaw itself. This is a *controller*.
- Not a multi-user SaaS. Single operator, single machine.
- Not a residential-proxy product. Exit-node routing is supported via Tailscale
  but not owned by this app.

## User stories

1. **Daily chat**  — I open my laptop, the VM is already running, I click the tray
   icon, the chat window appears, I talk to my agent.
2. **Zero maintenance** — If the VM crashes, ClawDeck restarts it. If the tunnel URL
   rotates, the Azure/Cloudflare/allowed-origins config updates automatically.
3. **Remote usability** — The public tunnel URL is pushed to my phone via a
   QR code or a copied link, so the same agent is reachable from anywhere.
4. **At-a-glance status** — Tray icon colour tells me instantly whether the stack
   is healthy.
5. **Safe secrets** — The gateway password is never in a text file; it lives in
   Windows Credential Manager / macOS Keychain / Linux Secret Service.
6. **Open source friendly** — Anyone can fork, audit, self-host; MIT-licensed.

## Component map

```
┌──────────────────────────────────────────────────────────────┐
│                         ClawDeck (desktop app)               │
│                                                              │
│   ┌─────────────────┐     ┌────────────────────────────┐     │
│   │   System tray   │─────│    Flet main window        │     │
│   │   (pystray)     │     │  Home · Chat · Logs · Set  │     │
│   └────────┬────────┘     └──────────────┬─────────────┘     │
│            │                             │                   │
│            └──────────┬──────────────────┘                   │
│                       │                                      │
│   ┌───────────────────▼───────────────────────────────────┐  │
│   │                   Core services                       │  │
│   │                                                       │  │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│   │  │   VM     │ │ Gateway  │ │  Tunnel  │ │ Monitor  │  │  │
│   │  │ control  │ │  client  │ │ watcher  │ │  loop    │  │  │
│   │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │  │
│   └───────┼────────────┼────────────┼────────────┼────────┘  │
│           │            │            │            │           │
│   ┌───────▼───┐ ┌──────▼─────┐ ┌────▼─────┐ ┌────▼───────┐   │
│   │VBoxManage │ │ ws://127…  │ │guestctrl │ │ event bus  │   │
│   │  (.exe)   │ │  auth+rpc  │ │ (tunnel  │ │  (asyncio) │   │
│   │           │ │            │ │  log)    │ │            │   │
│   └───────────┘ └────────────┘ └──────────┘ └────────────┘   │
│                                                              │
│   ┌───────────────────────────────────────────────────────┐  │
│   │               Config & secrets                         │ │
│   │   TOML at %APPDATA%/ClawDeck/config.toml               │ │
│   │   Secrets via keyring (Credential Manager/Keychain)    │ │
│   └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
   ┌─────────────────────────────────┐
   │  VirtualBox VM (existing)       │
   │  ────────────────────────────── │
   │  systemd: openclaw-gateway      │
   │  systemd: openclaw-tunnel       │
   │  Cloudflare Quick Tunnel        │
   └─────────────────────────────────┘
```

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | **Python 3.11+** | Already installed on the target, simplest cross-platform runtime |
| UI framework | **Flet** | Flutter-quality UI from Python; single-file app; dark/light built-in |
| System tray | **pystray** | Mature cross-platform tray library |
| Async runtime | **asyncio** | Stdlib; plays well with Flet and websockets |
| Gateway client | **websockets** | Pure Python, RFC-compliant, 1M+ downloads/day |
| HTTP | **httpx** | Async, typed, modern successor to requests |
| Secrets | **keyring** | Cross-platform credential store bridge |
| Config format | **TOML** (tomllib stdlib + tomli_w) | Human-readable, typed, no ambiguity |
| Packaging | **PyInstaller** (single-file exe) | No Python install required on user machines |
| Dep manager | **uv** | 10-100× faster than pip, used during dev |
| Lint/format | **ruff** | Single tool, fast |
| Type check | **pyright** | Strict optional; runs in CI |
| Tests | **pytest** + **pytest-asyncio** | Standard |

## Runtime model

The app has **three concurrent subsystems** inside a single process:

1. **asyncio event loop** — core monitoring, gateway WS, tunnel watcher, all async
2. **Flet window** — runs its own event loop; UI events are marshalled to asyncio
   via a thread-safe queue
3. **pystray** — runs on its own thread (Windows needs the tray to own the message
   pump); communicates via the same shared event bus

A single shared `AppState` object (asyncio-safe, observable) is the source of truth.
All three subsystems read from it; the monitor loop is the only writer for status
fields.

## Process lifecycle

```
Windows login
   └─> Registry Run key launches `clawdeck.exe`
         └─> config load (default if absent)
             └─> ensure VM started (VBoxManage startvm --type headless)
                 └─> start monitor loop
                     ├─> tray icon appears (status=starting)
                     └─> gateway health polling (~5s)
                         └─> when gateway ok: status=healthy (tray turns green)
                             └─> fetch current tunnel URL
                                 └─> update origins config if changed
```

On quit:
- Tray "Quit" by default **does not** stop the VM — user might still be using
  OpenClaw via the tunnel on another device. A second menu entry "Quit + stop VM"
  exists for full shutdown.

## State model

```python
@dataclass
class AppState:
    vm: VmState                 # running | stopped | paused | unknown
    gateway: GatewayState       # reachable | auth_required | unreachable | error
    tunnel: TunnelState         # up | down | rotating
    tunnel_url: str | None
    agent_last_reply_at: datetime | None
    tokens_today: int
    errors: list[AppError]
```

The UI subscribes to state diffs; any changed field triggers a re-render of the
affected panel only.

## Security model

- **No plaintext secrets on disk.** Gateway password lives in the OS credential store.
- **TOML config** holds non-secret operational data only (VM name, port, theme).
- **Windows Credential Manager** entry: service=`ClawDeck`, user=`gateway`.
- **No outbound telemetry.** Fully local-first. An optional update-check pings a
  GitHub Releases endpoint; user can disable it.
- **Code signing** (eventual) for the Windows .exe to avoid SmartScreen warnings.
  Not in Phase 1.

## Config file shape

`%APPDATA%/ClawDeck/config.toml` (on Windows)

```toml
[app]
theme = "auto"         # auto | light | dark
autostart = true
check_updates = true

[vm]
name = "OpenClaw"
provider = "virtualbox"          # future: hyperv, wsl2, remote-ssh
headless = true
autostart_vm = true
vboxmanage_path = ""             # auto-detected if empty

[gateway]
host = "127.0.0.1"
port = 18789
scheme = "ws"
tls_verify = true

[tunnel]
type = "cloudflared"             # cloudflared | tailscale | manual
detect_from_vm = true
fallback_url = ""

[chat]
persist_history = true
history_dir = ""                 # default: %APPDATA%/ClawDeck/chats
```

## Error handling

Three classes of errors, distinguished in the UI:

1. **Transient** (tunnel briefly down, gateway restarting) — silently retry with
   backoff, tray icon goes yellow, no toast.
2. **Actionable** (wrong password, VM missing, VBoxManage not found) — toast
   notification, opens settings to relevant section, tray icon red.
3. **Fatal** (app dependency missing) — modal dialog, logs path shown, no tray.

## Phases

### Phase 1 — MVP *(this plan)*
Scope: tray, status monitoring, VM start/stop, open-dashboard, settings, auto-start.
Target: usable single-file .exe on Windows 11.

### Phase 2 — Polish
Embedded chat, live log viewer, QR code for mobile tunnel URL, cost tracker,
notifications on agent reply, multiple profiles (local/VPS).

### Phase 3 — Beyond
- macOS + Linux builds
- Tailscale exit-node integration
- Plugin system for custom channels (Telegram etc.)
- Remote ClawDeck-to-ClawDeck federation (manage multiple stacks)
- Built-in backup manager

## Success criteria for Phase 1

- [ ] Single-file `clawdeck.exe` under 60 MB
- [ ] First-run wizard completes in < 60 seconds
- [ ] Tray icon reflects status within 10 seconds of any state change
- [ ] VM auto-starts on Windows login
- [ ] Dashboard opens in default browser on one click
- [ ] No crashes under 24 hours of continuous use
- [ ] Works with the *existing* OpenClaw setup without any VM-side changes

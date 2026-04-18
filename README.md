# ClawDeck

**Personal desktop control panel for [OpenClaw](https://openclaw.ai) agents.**

A single Windows app that manages your full OpenClaw stack — auto-starts your
VirtualBox VM on login, keeps the gateway and Cloudflare tunnel healthy, gives
you a tray-icon status at a glance, and opens a native chat + dashboard when
you need it.

> Built for the "I run OpenClaw on a home VM and want it to Just Work" use
> case. Open source, local-first, zero telemetry.

---

## Features

- 🖥️ **Tray-first UX** — one-glance status; one-click chat
- 🚀 **Auto-starts everything** on Windows login (VM, gateway, tunnel)
- 💬 **Native chat** with your agent without leaving the app
- 📊 **Live status** — VM, gateway, tunnel, agent monitored every few seconds
- 🔗 **Tunnel URL auto-discovery** — copies the current `trycloudflare.com`
  URL to clipboard or your phone in one click
- 🔒 **Secrets in OS keychain** — no plaintext passwords on disk
- 🌓 **Auto theme** — respects Windows light/dark preference
- 📦 **Single-file `clawdeck.exe`** (~25 MB) — no Python install needed
- 🏠 **Local-first** — no telemetry, no account, no cloud dependency

## Screenshots

*Coming once the build is out of alpha.*

## Quick start

### Requirements

- Windows 10 (build 1809+) or Windows 11
- [VirtualBox](https://www.virtualbox.org/) with an OpenClaw VM
- OpenClaw gateway listening inside the VM (default port `18789`)

### Install

Download `clawdeck.exe` from the Releases page, then from PowerShell:

```powershell
.\scripts\install_windows.ps1 -Source .\clawdeck.exe
```

This copies the binary to `%LOCALAPPDATA%\ClawDeck\`, registers a HKCU Run key
for autostart, adds a Start Menu shortcut, and removes any legacy
`OpenClaw-AutoStart` scheduled task.

### From source

```powershell
git clone https://github.com/ulyssespuzon/clawdeck
cd clawdeck
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
clawdeck
```

### First-run setup

Open the Settings tab and fill in:

| Field | What to put |
|-------|-------------|
| VM name | Your VirtualBox display name (default `OpenClaw`) |
| Guest user / password | Linux login used for `VBoxManage guestcontrol` (optional) |
| Gateway host + port | `127.0.0.1` + `18789` (defaults) |
| Gateway password | The `gateway.auth.password` you set during OpenClaw onboarding |

Secrets live in Windows Credential Manager under the `ClawDeck` service.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                     ClawDeck (desktop)                  │
│                                                         │
│   Tray (pystray) ─────────┬──── Flet window            │
│                           │                            │
│          ┌────────────────▼────────────────┐           │
│          │      Monitor loop (asyncio)      │           │
│          └────┬────────┬────────┬────┬─────┘           │
│           VM │   GW   │ Tunnel │ State bus             │
└──────────────┼────────┼────────┼──────────────────────┘
               │        │        │
               ▼        ▼        ▼
         VBoxManage   ws://    guestctrl → /var/log
                      gateway
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full component map,
state model, and runtime design.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — component map + runtime
- [`docs/SETUP.md`](docs/SETUP.md) — step-by-step install
- [`docs/FEATURES.md`](docs/FEATURES.md) — what's in each phase
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — contributor guide
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — current state

## Roadmap

**Phase 1** *(shipped)* — Tray, status, chat, settings, single-file build
**Phase 2** — QR code for mobile, toast notifications, cost tracker, profiles
**Phase 3** — macOS + Linux, Tailscale exit-node, plugin system, federation

## Contributing

PRs welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Licence

MIT — see [`LICENSE`](LICENSE).

## Why?

OpenClaw is great. The self-hosted workflow — VirtualBox VM + gateway +
Cloudflare tunnel + systemd + browser dashboard — is not. ClawDeck wraps that
into a single-binary desktop app so you can stop thinking about it.

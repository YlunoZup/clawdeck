# Project status — Phase 2 complete

## Build artefacts

| Artefact | Path | Size |
|----------|------|------|
| Single-file Windows exe | `dist/clawdeck.exe` | ~24.6 MB |
| Python package | `src/clawdeck/` | 28 files |
| Tests | `tests/` | **36 unit tests, all green** |
| Docs | `docs/` | 6 markdown files |
| Scripts | `scripts/` | build, dev, install, uninstall |
| CI | `.github/workflows/ci.yml` | 3.11/3.12/3.13 × Windows/Linux |
| Licence | MIT | `LICENSE` |

## Phase 1 ✅

Tray, status monitoring, VM control, gateway client, tunnel detection,
first-time-usable window, single-file exe.

## Phase 2 ✅

- **Chat persistence** — SQLite `chats.db`; session switcher
- **Toast notifications** — WinRT native on status transitions
- **QR code** — scan with phone to open tunnel URL
- **Log filters + search** — level dropdown, substring search, auto-follow
- **Multi-profile scaffold** — local / VPS / Tailscale templates
- **Usage tab** — cost + tokens, per provider / per day
- **Cron tab** — list/add/remove/toggle scheduled jobs
- **Origin auto-sync** — tunnel URL rotation updates allowedOrigins + restarts gateway
- **First-run wizard** — guided setup on first launch

## Package layout (Phase 2)

```
src/clawdeck/
├── __init__.py
├── __main__.py           # python -m clawdeck
├── cli.py                # Main entry (absolute imports for PyInstaller)
├── app.py                # Orchestrator
├── config.py
├── models.py
├── secrets.py
├── logging_setup.py
├── profiles.py           # NEW (P2)
├── core/
│   ├── vm.py
│   ├── gateway.py
│   ├── tunnel.py
│   ├── monitor.py
│   ├── history.py        # NEW (P2)
│   ├── origin_sync.py    # NEW (P2)
│   ├── usage.py          # NEW (P2)
│   └── cron.py           # NEW (P2)
├── services/
│   ├── autostart.py
│   └── notify.py         # NEW (P2)
├── ui/
│   ├── icons.py
│   ├── tray.py
│   ├── window.py
│   ├── wizard.py         # NEW (P2)
│   ├── components/
│   │   ├── status_card.py
│   │   └── qr.py         # NEW (P2)
│   └── views/
│       ├── home.py       # expanded (QR)
│       ├── chat.py       # expanded (sessions)
│       ├── logs.py       # expanded (filters)
│       ├── settings.py
│       ├── usage.py      # NEW (P2)
│       └── cron.py       # NEW (P2)
└── utils/
    ├── paths.py
    └── platform.py
```

## Acceptance — Phase 2

| Criterion | Target | Actual |
|-----------|--------|--------|
| `clawdeck.exe` size | < 60 MB | 24.6 MB ✓ |
| Cold-start to tray icon | < 10 s | ~3–5 s ✓ |
| Tests green | 100% | 36/36 ✓ |
| Ruff clean | 0 | 0 ✓ |
| Chat history persists across restarts | Yes | ✓ |
| Tunnel URL rotation auto-syncs gateway | Yes | ✓ |
| Toast fires on state transition | Yes | ✓ (WinRT) |

## What's next (Phase 3)

- macOS + Linux builds
- Tailscale exit-node wiring + UI
- Plugin system (drop `.py` in `~/.clawdeck/plugins/`)
- Remote ClawDeck federation — manage multiple stacks from one UI
- Code signing for the .exe (SmartScreen)
- Auto-update via GitHub Releases
- Embedded dashboard webview once Flet's webview matures
- Resource graphs (CPU/RAM inside the VM)

# Contributing to ClawDeck

Thanks for considering a contribution.

## Scope

ClawDeck is a *thin controller* around OpenClaw, VirtualBox, and a tunnel service.
Features that belong in this repo:

- Desktop UX improvements (tray, window, notifications, themes)
- VM provider support (Hyper-V, WSL2, remote SSH)
- Tunnel provider support (Tailscale, ngrok, named Cloudflare tunnels)
- Cross-platform builds
- Auto-update infrastructure

Features that **do not** belong here (upstream to OpenClaw instead):

- Agent logic
- Model provider integrations
- Chat/memory/tools
- Channel connectors (Telegram, Discord, etc.)

## Dev setup

```powershell
git clone https://github.com/<you>/clawdeck
cd clawdeck
uv sync --dev
uv run clawdeck
```

Tests:
```powershell
uv run pytest
```

Lint + format:
```powershell
uv run ruff check .
uv run ruff format .
```

Type-check:
```powershell
uv run pyright
```

## Pull requests

- One feature/fix per PR
- Include tests for new logic (monitor loop, VM control, config parsing)
- Update `docs/` if behavior changes
- CI must be green

## Commit style

Short imperative subject, ~50 chars. Detailed body if useful. Example:

```
Add Hyper-V VM provider

Introduces `VmProvider.HyperV` that wraps PowerShell `Get-VM`,
`Start-VM`, `Stop-VM`. Config gains `vm.provider = "hyperv"`.
```

## Code of Conduct

Be kind. Ask before assuming. No harassment.

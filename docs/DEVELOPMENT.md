# Development

## Layout

```
clawdeck/
├── src/clawdeck/              # The package
│   ├── __main__.py            # Entry: wires tray + window + asyncio
│   ├── app.py                 # App orchestrator (state, core services)
│   ├── models.py              # AppState, VmState, GatewayState, ...
│   ├── config.py              # TOML load/save
│   ├── secrets.py             # keyring wrapper
│   ├── logging_setup.py       # RotatingFileHandler
│   ├── core/
│   │   ├── vm.py              # VBoxManage wrapper
│   │   ├── gateway.py         # OpenClaw WS client
│   │   ├── tunnel.py          # trycloudflare URL watcher
│   │   └── monitor.py         # Polling loop + event bus
│   ├── services/
│   │   └── autostart.py       # HKCU Run key
│   ├── ui/
│   │   ├── tray.py            # pystray integration
│   │   ├── window.py          # Flet main window shell
│   │   ├── icons.py           # PIL-generated tray icons
│   │   ├── components/        # Shared widgets
│   │   └── views/             # Home / Chat / Logs / Settings
│   └── utils/
│       ├── paths.py           # platformdirs
│       └── platform.py        # OS detection + VBoxManage lookup
├── tests/                     # pytest
├── scripts/                   # build.py, dev.py, install_windows.ps1, ...
├── docs/                      # ARCHITECTURE, FEATURES, SETUP, this file
└── assets/                    # Eventual icon.ico
```

## Local dev

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts\dev.py       # or: python -m clawdeck
```

## Tests + lint

```powershell
pytest -q
ruff check src/
pyright
```

## Building the .exe

```powershell
python scripts\build.py
# Output: dist\clawdeck.exe
```

## Installing locally

```powershell
.\scripts\install_windows.ps1
```

## Debugging tips

- **App log:** `%APPDATA%\ClawDeck\Logs\clawdeck.log` (rotates at 5MB × 5 files)
- **Config:** `%APPDATA%\ClawDeck\config.toml`
- **Secrets:** `Credential Manager → Windows Credentials → ClawDeck`
- **Clear everything:** `scripts\uninstall_windows.ps1 -Purge`

## Hot-reloading the UI

Flet supports hot reload in dev mode. Export `FLET_HOT_RELOAD=1` before running
`python scripts\dev.py`.

## Code style

- Ruff handles both format and lint (`ruff format`, `ruff check`)
- Imports are sorted with ruff's isort rules, `known-first-party = ["clawdeck"]`
- Type hints required on public methods; tests may skip
- `from __future__ import annotations` at the top of every module

## Adding a new tab

1. Create `src/clawdeck/ui/views/myview.py` following `home.py` as a template
2. Register it in `ui/window.py` inside the `ft.Tabs` list
3. If it needs state updates, wire `update_from_state(state: AppState)` and
   call it from `MainWindow.on_state`

## Adding a new monitored field

1. Extend `models.AppState` with the field + default value
2. Emit it from a new / existing poller in `core/monitor.py`
3. Update the Home view to render it

## Adding a new VM provider

Implement the same method signatures as `core/vm.VmController`:
- `exists`, `info`, `state`, `start`, `stop`, `pause`, `resume`,
  `ensure_running`, `guest_exec`

Then branch in `app.App.assemble()` on `config.vm.provider`.

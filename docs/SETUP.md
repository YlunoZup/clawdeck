# ClawDeck — Setup guide

## Prerequisites

- Windows 10 (build 1809+) or Windows 11
- [VirtualBox 7.0+](https://www.virtualbox.org/) with an OpenClaw VM already
  created and working
- An OpenClaw gateway running inside that VM on port 18789 (default)

## 1 · Install

**Option A — pre-built binary (recommended)**

Download the latest `clawdeck.exe` from the Releases page, then from PowerShell:

```powershell
.\scripts\install_windows.ps1 -Source .\clawdeck.exe
```

This:
- Copies the binary to `%LOCALAPPDATA%\ClawDeck\clawdeck.exe`
- Adds a Start Menu shortcut
- Registers HKCU autostart
- Cleans up the legacy `OpenClaw-AutoStart` scheduled task if present

**Option B — from source**

```powershell
git clone https://github.com/ulyssespuzon/clawdeck
cd clawdeck
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
clawdeck        # or `python -m clawdeck`
```

## 2 · First-run wizard

On the first launch, ClawDeck opens the Settings tab so you can fill in:

| Field | What to put |
|-------|-------------|
| VM name | The VirtualBox display name (default: `OpenClaw`) |
| Guest user | Linux username inside the VM (default: `vboxuser`) |
| Guest password | Linux password — only needed for tunnel-log tailing |
| Gateway host + port | `127.0.0.1` + `18789` unless you changed it |
| Gateway password | The `gateway.auth.password` you set during OpenClaw onboarding |

Secrets (guest password, gateway password) are stored in Windows Credential
Manager under the `ClawDeck` service. They never touch disk.

## 3 · Daily usage

- **Tray icon** — right-click for quick actions, left-click to open main window
- **Chat tab** — talk to the agent directly inside ClawDeck
- **Home tab** — status of VM, gateway, tunnel at a glance
- **Logs tab** — live tail of `clawdeck.log`

Close the main window with the `×` button and the app hides to tray; it keeps
running. Use the tray menu → Quit to exit fully.

## Configuration file location

`%APPDATA%\ClawDeck\config.toml`

Editing it while the app is running takes effect on the next tray restart.

## Uninstall

```powershell
.\scripts\uninstall_windows.ps1           # keeps config + logs
.\scripts\uninstall_windows.ps1 -Purge    # also wipes %APPDATA%\ClawDeck
```

## Troubleshooting

### Tray icon is grey and stays grey

VM isn't detected. Check:
- VirtualBox installed and `VBoxManage` in PATH?
- `vm.name` in config matches the display name shown by `VBoxManage list vms`

### Gateway state stuck on `pairing_required`

Your device isn't approved yet. On the VM run:

```bash
openclaw devices list
openclaw devices approve <request-id>
```

Or use the existing dashboard once over HTTP → it prompts for approval.

### Chat says "No API key found for provider"

Model provider auth is missing on the OpenClaw side — not a ClawDeck bug. See
OpenClaw's `models auth` docs.

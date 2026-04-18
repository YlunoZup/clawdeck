<#
.SYNOPSIS
Installs ClawDeck for the current user.

.DESCRIPTION
- Copies clawdeck.exe to %LOCALAPPDATA%\ClawDeck
- Creates a Start Menu shortcut
- Registers the HKCU Run entry for autostart (optional flag)
- Removes the legacy "OpenClaw-AutoStart" scheduled task if present

.PARAMETER Source
Path to the freshly-built clawdeck.exe (default: .\dist\clawdeck.exe)

.PARAMETER NoAutostart
Skip registering autostart at Windows login.

.EXAMPLE
pwsh .\scripts\install_windows.ps1
#>

[CmdletBinding()]
param(
    [string]$Source = ".\dist\clawdeck.exe",
    [switch]$NoAutostart
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Source)) {
    throw "Source not found: $Source. Run `python scripts\build.py` first."
}

$installDir = Join-Path $env:LOCALAPPDATA "ClawDeck"
$target = Join-Path $installDir "clawdeck.exe"
New-Item -ItemType Directory -Path $installDir -Force | Out-Null

Write-Host "Copying -> $target"
Copy-Item $Source $target -Force

# Start Menu shortcut
$startMenu = [Environment]::GetFolderPath("StartMenu")
$shortcut = Join-Path $startMenu "Programs\ClawDeck.lnk"
$ws = New-Object -ComObject WScript.Shell
$shortcutObj = $ws.CreateShortcut($shortcut)
$shortcutObj.TargetPath = $target
$shortcutObj.WorkingDirectory = $installDir
$shortcutObj.IconLocation = "$target,0"
$shortcutObj.Description = "ClawDeck"
$shortcutObj.Save()
Write-Host "Shortcut -> $shortcut"

# Legacy scheduled task cleanup
$legacy = "OpenClaw-AutoStart"
$existing = Get-ScheduledTask -TaskName $legacy -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing legacy scheduled task: $legacy"
    Unregister-ScheduledTask -TaskName $legacy -Confirm:$false
}

# Registry Run key for autostart
if (-not $NoAutostart) {
    $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    New-ItemProperty -Path $runKey -Name "ClawDeck" -Value "`"$target`"" -PropertyType String -Force | Out-Null
    Write-Host "Autostart registered at HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
}

Write-Host ""
Write-Host "✓ ClawDeck installed. Launch from Start Menu or run:"
Write-Host "  $target"

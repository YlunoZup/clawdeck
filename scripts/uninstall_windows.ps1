<#
.SYNOPSIS
Removes ClawDeck, its autostart entry, and shortcut.

Leaves config + logs in %APPDATA%\ClawDeck untouched (pass -Purge to wipe them too).
#>

[CmdletBinding()]
param(
    [switch]$Purge
)

$ErrorActionPreference = "Continue"

# Autostart
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
if (Get-ItemProperty -Path $runKey -Name "ClawDeck" -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $runKey -Name "ClawDeck" -Force
    Write-Host "Removed autostart entry"
}

# Start Menu shortcut
$startMenu = [Environment]::GetFolderPath("StartMenu")
$shortcut = Join-Path $startMenu "Programs\ClawDeck.lnk"
if (Test-Path $shortcut) { Remove-Item $shortcut -Force }

# Installed binary
$installDir = Join-Path $env:LOCALAPPDATA "ClawDeck"
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
    Write-Host "Removed $installDir"
}

if ($Purge) {
    $roaming = Join-Path $env:APPDATA "ClawDeck"
    if (Test-Path $roaming) {
        Remove-Item $roaming -Recurse -Force
        Write-Host "Purged $roaming (config + logs)"
    }
}

Write-Host "✓ Uninstalled"

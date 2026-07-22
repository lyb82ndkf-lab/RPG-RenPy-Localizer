param(
    [string]$ApkPath = (Join-Path $PSScriptRoot "app/build/outputs/apk/debug/app-debug.apk"),
    [string]$PackageName = "com.rpgrtl.shell",
    [string]$LogPath = (Join-Path $PSScriptRoot "android-device-run.log")
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$adb = "D:/Android SDK/platform-tools/adb.exe"
if (-not (Test-Path $adb)) { $adb = "adb" }

.\build_apk.ps1
$ApkPath = (Resolve-Path $ApkPath).Path

$devices = & $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "\tdevice$" }
if (-not $devices -or $devices.Count -lt 1) {
    throw "No online Android device detected by adb. Connect a device with USB debugging enabled, then rerun this script."
}
if ($devices.Count -gt 1) {
    throw "Multiple Android devices detected. Disconnect extras or set ANDROID_SERIAL before running."
}

& $adb install -r $ApkPath
if ($LASTEXITCODE -ne 0) { throw "adb install failed with exit code $LASTEXITCODE" }

& $adb logcat -c
& $adb shell monkey -p $PackageName 1
if ($LASTEXITCODE -ne 0) { throw "App launch failed with exit code $LASTEXITCODE" }

Start-Sleep -Seconds 5
& $adb logcat -d > $LogPath

Write-Host "Installed and launched $PackageName."
Write-Host "Logcat saved to: $LogPath"
Write-Host "Manual verification still required: start a real RPG Maker/RenPy game, confirm the overlay, virtual keys, live translation, and data editing."

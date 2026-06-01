$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (Test-Path ".\gradlew.bat") {
    .\gradlew.bat assembleDebug
} else {
    gradle assembleDebug
}

Write-Host "APK output:"
Write-Host (Join-Path $Root "app\build\outputs\apk\debug\app-debug.apk")


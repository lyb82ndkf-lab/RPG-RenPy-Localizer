param(
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

if (!(Test-Path $Venv)) {
    python -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install pyinstaller

$Dist = Join-Path $Root $OutputDir
if (Test-Path $Dist) {
    Remove-Item -Recurse -Force $Dist
}

$Launcher = Join-Path $Root "main.py"

& $Python -m PyInstaller `
    --noconsole `
    --clean `
    --name "RPGRenPyLocalizer" `
    --distpath $Dist `
    --workpath (Join-Path $Root "build") `
    --specpath (Join-Path $Root "build") `
    $Launcher

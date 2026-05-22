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
& $Python -m pip install unrpa unrpyc
& $Python -m pip install git+https://github.com/CensoredUsername/unrpyc.git
if ($LASTEXITCODE -ne 0) {
    Write-Warning "unrpyc GitHub install failed; continuing with any already-installed local copy."
}

$Dist = Join-Path $Root $OutputDir
Get-Process -Name RPGRenPyLocalizer -ErrorAction SilentlyContinue | Stop-Process -Force
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

$GuideName = -join ([char[]](0x4f7f, 0x7528, 0x8bf4, 0x660e, 0x2e, 0x74, 0x78, 0x74))
$Readme = Join-Path $Root $GuideName
$PackageDir = Join-Path $Dist "RPGRenPyLocalizer"
if (Test-Path $Readme) {
    Copy-Item -LiteralPath $Readme -Destination (Join-Path $PackageDir $GuideName) -Force
}

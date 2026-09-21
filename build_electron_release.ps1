param(
    [switch]$SkipNpmInstall,
    [switch]$DirOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Invoke-CheckedNative {
    param([Parameter(Mandatory=$true)][scriptblock]$Command)
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Command
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        throw "Command execution failed with exit code: $exitCode"
    }
}

Write-Host "== RPGRenPyLocalizer Electron Build ==" -ForegroundColor Cyan

$Python = $null
$candidates = @()
try {
    $pyCandidate = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null)
    if ($pyCandidate) {
        $candidates += $pyCandidate.Trim()
    }
} catch {}
$candidates += @(
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe",
    (Join-Path $ProjectRoot ".build-venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    "python"
)

foreach ($candidate in $candidates) {
    try {
        & $candidate -c "import encodings" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $Python = $candidate
            break
        }
    } catch {
        continue
    }
}
if (-not $Python) {
    throw "No usable Python runtime found."
}

Write-Host "[1/4] Checking PyInstaller..." -ForegroundColor Cyan
try {
    & $Python -m PyInstaller --version | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller missing" }
} catch {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    Invoke-CheckedNative { & $Python -m pip install pyinstaller }
}

Write-Host "[2/4] Packaging Python API Backend..." -ForegroundColor Cyan
$BackendBuild = Join-Path $ProjectRoot "build\electron-backend"
$BackendDist = Join-Path $BackendBuild "rpgrtl-api"
if (Test-Path $BackendBuild) { Remove-Item -LiteralPath $BackendBuild -Recurse -Force }
New-Item -ItemType Directory -Force -Path $BackendBuild | Out-Null

Invoke-CheckedNative { & $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name rpgrtl-api `
    --distpath $BackendBuild `
    --workpath (Join-Path $ProjectRoot "build\pyinstaller-electron") `
    --specpath (Join-Path $ProjectRoot "build") `
    --collect-submodules toolkit `
    api_server_entry.py }

if (-not (Test-Path (Join-Path $BackendDist "rpgrtl-api.exe"))) {
    throw "Python backend build failed: rpgrtl-api.exe not found"
}

Write-Host "[3/4] Checking Electron dependencies..." -ForegroundColor Cyan
if (-not $SkipNpmInstall) {
    Invoke-CheckedNative { npm install }
}

Write-Host "[4/4] Building Electron application..." -ForegroundColor Cyan
if ($DirOnly) {
    Invoke-CheckedNative { npm run pack }
} else {
    Invoke-CheckedNative { npm run dist }
}

Write-Host "Build complete! Output directory: $ProjectRoot\release-electron" -ForegroundColor Green

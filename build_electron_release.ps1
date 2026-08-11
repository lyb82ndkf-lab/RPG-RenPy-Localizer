param(
    [switch]$SkipNpmInstall,
    [switch]$DirOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Invoke-CheckedNative {
    param([Parameter(Mandatory=$true)][scriptblock]$Command)
    # PyInstaller writes its progress stream to stderr.  Keep `Stop` for
    # PowerShell failures, but do not treat normal native stderr output as a
    # terminating error; the executable's exit code is authoritative.
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Command
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        throw "命令执行失败，退出码：$exitCode"
    }
}

Write-Host "== RPGRenPyLocalizer Electron 一体化构建 ==" -ForegroundColor Cyan

$Python = $null
foreach ($candidate in @(
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    (Join-Path $ProjectRoot ".build-venv\Scripts\python.exe"),
    "python"
)) {
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
    throw "未找到可用的 Python 运行时。"
}

Write-Host "[1/4] 检查 PyInstaller..." -ForegroundColor Cyan
try {
    & $Python -m PyInstaller --version | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller missing" }
} catch {
    Write-Host "安装 PyInstaller..." -ForegroundColor Yellow
    Invoke-CheckedNative { & $Python -m pip install pyinstaller }
}

Write-Host "[2/4] 打包 Python API 后端..." -ForegroundColor Cyan
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
    throw "Python 后端打包失败：未找到 rpgrtl-api.exe"
}

Write-Host "[3/4] 安装 Electron 依赖..." -ForegroundColor Cyan
if (-not $SkipNpmInstall) {
    Invoke-CheckedNative { npm install }
}

Write-Host "[4/4] 构建 Electron 应用..." -ForegroundColor Cyan
if ($DirOnly) {
    Invoke-CheckedNative { npm run pack }
} else {
    Invoke-CheckedNative { npm run dist }
}

Write-Host "构建完成。输出目录：$ProjectRoot\release-electron" -ForegroundColor Green

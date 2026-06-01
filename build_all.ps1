param(
    [string]$Version = "2.5",
    [switch]$Debug,
    [switch]$NoH5,
    [switch]$OnlyUniversal
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Mode = if ($Debug) { "debug" } else { "release" }
$Start = Get-Date

function Step([string]$Text) {
    Write-Host $Text -ForegroundColor Cyan
}

function Resolve-H5Output([string]$ProjectRoot) {
    $candidates = @(
        (Join-Path $ProjectRoot "unpackage\dist\build\web"),
        (Join-Path $ProjectRoot "unpackage\dist\build\h5"),
        (Join-Path $ProjectRoot "dist\build\h5"),
        (Join-Path $ProjectRoot "dist\build\web")
    )

    foreach ($candidate in $candidates) {
        $indexPath = Join-Path $candidate "index.html"
        $assetsPath = Join-Path $candidate "assets"
        if ((Test-Path $indexPath) -and (Test-Path $assetsPath)) {
            $jsFiles = Get-ChildItem -Path $assetsPath -Filter "*.js" -ErrorAction SilentlyContinue
            if ($jsFiles | Where-Object { $_.Length -gt 10000 }) {
                return $candidate
            }
        }
    }

    return $null
}

Write-Host "=== RPGRenPyLocalizer Android Build $Version ($Mode) ===" -ForegroundColor Green

$uniProject = Join-Path $Root "AndroidAPP\AndroidAPP"
$webDist = $null

if (-not $NoH5) {
    Step "[1/4] Build UniApp H5"
    Push-Location $uniProject
    try {
        & npm run build:h5
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "npm run build:h5 exited with code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

Step "[2/4] Validate And Sync H5 Assets"
$webDist = Resolve-H5Output $uniProject

if (-not $webDist) {
    throw @"
No valid H5 output found.

Expected one of these directories to contain:
- index.html
- assets\*.js

Checked under:
$uniProject

Please build H5 in HBuilderX GUI first, then rerun:
powershell -ExecutionPolicy Bypass -File .\build_all.ps1 -Version $Version -NoH5
"@
}

Write-Host "Using H5 output: $webDist" -ForegroundColor Green

$mobileUi = Join-Path $Root "android_app\mobile_ui"
$shellMobileUi = Join-Path $Root "android_app\shell\app\src\main\assets\mobile_ui"

if (Test-Path $mobileUi) {
    Remove-Item -LiteralPath $mobileUi -Recurse -Force
}
New-Item -ItemType Directory -Path $mobileUi -Force | Out-Null
Copy-Item -Path (Join-Path $webDist "*") -Destination $mobileUi -Recurse -Force

if (Test-Path $shellMobileUi) {
    Remove-Item -LiteralPath $shellMobileUi -Recurse -Force
}
New-Item -ItemType Directory -Path $shellMobileUi -Force | Out-Null
Copy-Item -Path (Join-Path $webDist "*") -Destination $shellMobileUi -Recurse -Force

foreach ($indexPath in @((Join-Path $mobileUi "index.html"), (Join-Path $shellMobileUi "index.html"))) {
    if (Test-Path $indexPath) {
        $html = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8
        $html = $html.Replace(", interactive-widget=overlays-content", "")
        $html = $html.Replace(", interactive-widget=resizes-content", "")
        [System.IO.File]::WriteAllText($indexPath, $html, [System.Text.UTF8Encoding]::new($false))
    }
}

Step "[3/4] Gradle Build"
$env:JAVA_HOME = "D:\java\jdk-21"
$env:ANDROID_HOME = "D:\Android SDK"
$env:ANDROID_SDK_ROOT = "D:\Android SDK"
$env:Path = "D:\java\jdk-21\bin;D:\gradle-9.5.1\bin;" + $env:Path

$shellDir = Join-Path $Root "android_app\shell"
Push-Location $shellDir
try {
    if ($Debug) {
        & "D:\gradle-9.5.1\bin\gradle.bat" --no-daemon assembleDebug
    } else {
        & "D:\gradle-9.5.1\bin\gradle.bat" --no-daemon assembleRelease
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle build failed: $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Step "[4/4] Archive APK"
$archiveDir = Join-Path $Root "dist\android\$Version"
$latestDir = Join-Path $Root "dist\android\latest"
New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
if (Test-Path $latestDir) {
    Remove-Item -LiteralPath $latestDir -Recurse -Force
}
New-Item -ItemType Directory -Path $latestDir -Force | Out-Null

$apkRoot = Join-Path $Root "android_app\shell\app\build\outputs\apk\$Mode"
$pattern = if ($Debug) { "*.apk" } else { "*release.apk" }
$outputs = Get-ChildItem -Path $apkRoot -Filter $pattern
if ($OnlyUniversal) {
    $outputs = $outputs | Where-Object { $_.Name -match "universal" }
}

foreach ($apk in $outputs) {
    $abi = if ($apk.Name -match "arm64") {
        "arm64-v8a"
    } elseif ($apk.Name -match "armeabi") {
        "armeabi-v7a"
    } elseif ($apk.Name -match "universal") {
        "universal"
    } else {
        "android"
    }
    $kind = if ($Debug) { "debug" } else { "release-signed" }
    $targetName = "RPGRenPyLocalizer-$Version-$abi-$kind.apk"
    Copy-Item -LiteralPath $apk.FullName -Destination (Join-Path $archiveDir $targetName) -Force
    Copy-Item -LiteralPath $apk.FullName -Destination (Join-Path $latestDir $targetName) -Force
}

$readme = Join-Path $Root "dist\android\README.txt"
@"
RPGRenPyLocalizer Android install guide

Recommended:
- universal release signed APK: works on all supported Android devices.
- arm64-v8a release signed APK: smaller, for most modern phones.
- armeabi-v7a release signed APK: for old 32-bit phones.

Latest build: dist/android/latest/
Version archive: dist/android/<version>/
"@ | Set-Content -LiteralPath $readme -Encoding UTF8

Get-ChildItem -Path $archiveDir -Filter "*.apk" |
    Select-Object Name, @{ Name = "SizeMB"; Expression = { [math]::Round($_.Length / 1MB, 2) } }

$elapsed = (Get-Date) - $Start
Write-Host "=== Done in $([math]::Round($elapsed.TotalSeconds, 1))s ===" -ForegroundColor Green

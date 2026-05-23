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

function Find-HBuilderCli {
    $candidates = @("D:\HBuilderX\cli.exe", "E:\HBuilderX\cli.exe")
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    throw "HBuilderX cli.exe not found."
}

Write-Host "=== RPGRenPyLocalizer Android Build $Version ($Mode) ===" -ForegroundColor Green

if (-not $NoH5) {
    Step "[1/4] Build UniApp H5"
    $cli = Find-HBuilderCli
    $env:Path = (Split-Path $cli) + ";" + $env:Path
    $uniProject = Join-Path $Root "AndroidAPP\AndroidAPP"
    & $cli publish web --project $uniProject --webTitle RPGRenPyLocalizer --sourceMap false
    if ($LASTEXITCODE -ne 0) { throw "HBuilderX build failed: $LASTEXITCODE" }
}

Step "[2/4] Sync H5 assets"
$webDist = Join-Path $Root "AndroidAPP\AndroidAPP\unpackage\dist\build\web"
$mobileUi = Join-Path $Root "android_app\mobile_ui"
if (-not (Test-Path $webDist)) { throw "H5 output not found: $webDist" }
if (Test-Path $mobileUi) { Remove-Item -LiteralPath $mobileUi -Recurse -Force }
New-Item -ItemType Directory -Path $mobileUi | Out-Null
Copy-Item -Path (Join-Path $webDist "*") -Destination $mobileUi -Recurse -Force

Step "[3/4] Gradle build"
$env:JAVA_HOME = "D:\java\jdk-21"
$env:ANDROID_HOME = "D:\Android SDK"
$env:ANDROID_SDK_ROOT = "D:\Android SDK"
$env:Path = "D:\java\jdk-21\bin;D:\gradle-9.5.1\bin;" + $env:Path
$shellDir = Join-Path $Root "android_app\shell"
Push-Location $shellDir
try {
    if ($Debug) {
        & "D:\gradle-9.5.1\bin\gradle.bat" assembleDebug
    } else {
        & "D:\gradle-9.5.1\bin\gradle.bat" assembleRelease
    }
    if ($LASTEXITCODE -ne 0) { throw "Gradle build failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}

Step "[4/4] Archive APK"
$archiveDir = Join-Path $Root "dist\android\$Version"
$latestDir = Join-Path $Root "dist\android\latest"
New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
if (Test-Path $latestDir) { Remove-Item -LiteralPath $latestDir -Recurse -Force }
New-Item -ItemType Directory -Path $latestDir -Force | Out-Null

$apkRoot = Join-Path $Root "android_app\shell\app\build\outputs\apk\$Mode"
$pattern = if ($Debug) { "*.apk" } else { "*release.apk" }
$outputs = Get-ChildItem $apkRoot -Filter $pattern
if ($OnlyUniversal) {
    $outputs = $outputs | Where-Object { $_.Name -match "universal" }
}
foreach ($apk in $outputs) {
    $abi = if ($apk.Name -match "arm64") { "arm64-v8a" } elseif ($apk.Name -match "armeabi") { "armeabi-v7a" } elseif ($apk.Name -match "universal") { "universal" } else { "android" }
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

Get-ChildItem $archiveDir -Filter "*.apk" | Select-Object Name,@{Name="SizeMB";Expression={[math]::Round($_.Length/1MB,2)}}
$elapsed = (Get-Date) - $Start
Write-Host "=== Done in $([math]::Round($elapsed.TotalSeconds, 1))s ===" -ForegroundColor Green

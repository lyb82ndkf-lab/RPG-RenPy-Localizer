$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:JAVA_HOME = "D:\java\jdk-17"
$env:Path = "$env:JAVA_HOME\bin;" + $env:Path
$env:GRADLE_OPTS = "-Xmx4096m -XX:MaxMetaspaceSize=1024m -Dfile.encoding=UTF-8"


if (-not (Test-Path (Join-Path $Root "local.properties"))) {
    throw "Missing local.properties. Copy local.properties.template and point sdk.dir at your Android SDK."
}

if (Test-Path ".\gradlew.bat") {
    .\gradlew.bat clean assembleDebug
} elseif (Get-Command gradle -ErrorAction SilentlyContinue) {
    gradle clean assembleDebug
} elseif (Test-Path "D:\gradle-9.5.1\bin\gradle.bat") {
    & "D:\gradle-9.5.1\bin\gradle.bat" --no-daemon clean assembleDebug
} else {
    throw "Gradle was not found. Add Gradle to PATH or provide gradlew.bat."
}

if ($LASTEXITCODE -ne 0) {
    throw "Gradle assembleDebug failed with exit code $LASTEXITCODE."
}

$Apk = Join-Path $Root "app\build\outputs\apk\debug\app-debug.apk"
if (-not (Test-Path $Apk)) {
    throw "Gradle completed but APK was not created: $Apk"
}

$GradleText = Get-Content -Raw (Join-Path $Root "app\build.gradle")
$VersionMatch = [regex]::Match($GradleText, 'versionName\s+"([^"]+)"')
if (-not $VersionMatch.Success) {
    throw "Unable to determine Android versionName from app/build.gradle"
}

Write-Host "APK output:"
Write-Host $Apk

$Verifier = Join-Path $Root "tools\verify_apk.ps1"
if (Test-Path $Verifier) {
    & $Verifier -ApkPath $Apk
    if ($LASTEXITCODE -ne 0) {
        throw "APK verification failed with exit code $LASTEXITCODE."
    }
}

$DistDir = [System.IO.Path]::GetFullPath((Join-Path $Root "..\dist"))
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
$DistApk = Join-Path $DistDir ("RPGRenPyLocalizer-v{0}-arm64-compose.apk" -f $VersionMatch.Groups[1].Value)
Copy-Item -LiteralPath $Apk -Destination $DistApk -Force
Write-Host "Packaged distribution:"
Write-Host $DistApk

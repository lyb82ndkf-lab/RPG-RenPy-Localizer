$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:JAVA_HOME = "D:\java\jdk-17"
$env:Path = "$env:JAVA_HOME\bin;" + $env:Path

if (-not (Test-Path (Join-Path $Root "local.properties"))) {
    throw "Missing local.properties. Copy local.properties.template and point sdk.dir at your Android SDK."
}

if (Test-Path ".\gradlew.bat") {
    .\gradlew.bat assembleDebug
} elseif (Get-Command gradle -ErrorAction SilentlyContinue) {
    gradle assembleDebug
} elseif (Test-Path "D:\gradle-9.5.1\bin\gradle.bat") {
    & "D:\gradle-9.5.1\bin\gradle.bat" --no-daemon assembleDebug
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

Write-Host "APK output:"
Write-Host $Apk

$Verifier = Join-Path $Root "tools\verify_apk.ps1"
if (Test-Path $Verifier) {
    & $Verifier -ApkPath $Apk
    if ($LASTEXITCODE -ne 0) {
        throw "APK verification failed with exit code $LASTEXITCODE."
    }
}

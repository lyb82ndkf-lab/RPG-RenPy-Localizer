param(
    [string]$ApkPath = (Join-Path (Split-Path $PSScriptRoot -Parent) "app/build/outputs/apk/debug/app-debug.apk")
)

$ErrorActionPreference = "Stop"
$ApkPath = (Resolve-Path $ApkPath).Path
Add-Type -AssemblyName System.IO.Compression.FileSystem

function New-Text([int[]]$codepoints) {
    $chars = foreach ($cp in $codepoints) { [char]$cp }
    return -join $chars
}

$requiredLibraries = @(
    "libwinlator.so",
    "libvirglrenderer.so",
    "libvortekrenderer.so",
    "libgladiorenderer.so",
    "libmidihandler.so",
    "libfile_redirect_hook.so",
    "libgsl_alloc_hook.so",
    "libhook_impl.so",
    "libmain_hook.so"
)

$requiredUiStrings = @(
    "RPGRenPyLocalizer",
    "OpenAI",
    "Anthropic",
    "Ollama",
    "RPGMaker",
    "RenPy"
)

$requiredBridgeStrings = @(
    "androidAiSettings",
    "androidAiTranslate",
    "androidAiModels",
    "androidSaveTranslationEntries",
    "androidTranslationEntries"
)

function Read-ZipText($zip, [string]$entryName) {
    $entry = $zip.GetEntry($entryName)
    if ($null -eq $entry) { throw "Missing APK entry: $entryName" }
    $reader = [System.IO.StreamReader]::new($entry.Open(), [System.Text.Encoding]::UTF8)
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}

function Add-AssetDependency([System.Collections.Generic.HashSet[string]]$set, [string]$name) {
    if (-not $set.Contains($name)) { [void]$set.Add($name) }
}

$zip = [System.IO.Compression.ZipFile]::OpenRead($ApkPath)
try {
    $entryNames = @($zip.Entries | ForEach-Object { $_.FullName })

    foreach ($lib in $requiredLibraries) {
        $name = "lib/arm64-v8a/$lib"
        if ($entryNames -notcontains $name) { throw "Missing required Winlator engine library in APK: $name" }
    }

    $profileEntries = @($entryNames | Where-Object { $_ -like "assets/inputcontrols/profiles/*.icp" })
    if ($profileEntries.Count -lt 2) { throw "Expected at least two touchscreen control profiles in APK; found $($profileEntries.Count)." }
    foreach ($profileEntry in $profileEntries) {
        $profileJson = Read-ZipText $zip $profileEntry
        $profile = $profileJson | ConvertFrom-Json
        if (-not $profile.name) { throw "Input controls profile has no name: $profileEntry" }
        if (-not $profile.elements -or $profile.elements.Count -lt 1) { throw "Input controls profile has no elements: $profileEntry" }
    }

    $index = Read-ZipText $zip "assets/mobile_ui/index.html"
    $neededAssets = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($m in [regex]::Matches($index, '(?:src|href)="\.\/assets\/([^"#?]+)"')) {
        Add-AssetDependency $neededAssets $m.Groups[1].Value
    }

    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($asset in @($neededAssets)) {
            if (-not $asset.EndsWith(".js")) { continue }
            $entry = $zip.GetEntry("assets/mobile_ui/assets/$asset")
            if ($null -eq $entry) { throw "Referenced JS asset missing: assets/mobile_ui/assets/$asset" }
            $js = Read-ZipText $zip "assets/mobile_ui/assets/$asset"
            foreach ($m in [regex]::Matches($js, '["'']\.\/([^"''\\]+\.(?:js|css))["'']')) {
                $dep = $m.Groups[1].Value
                if (-not $neededAssets.Contains($dep)) {
                    [void]$neededAssets.Add($dep)
                    $changed = $true
                }
            }
        }
    }

    foreach ($asset in $neededAssets) {
        if ($entryNames -notcontains "assets/mobile_ui/assets/$asset") {
            throw "Referenced mobile UI asset missing from APK: $asset"
        }
    }

    $packagedAssets = @($entryNames | Where-Object { $_ -like "assets/mobile_ui/assets/*" } | ForEach-Object { $_.Substring("assets/mobile_ui/assets/".Length) })
    $staleAssets = @($packagedAssets | Where-Object { -not $neededAssets.Contains($_) })
    if ($staleAssets.Count -gt 0) {
        throw "APK contains stale/unreferenced mobile UI assets: $($staleAssets -join ', ')"
    }

    $uiText = ""
    foreach ($asset in $neededAssets) {
        if ($asset.EndsWith(".js")) { $uiText += "`n" + (Read-ZipText $zip "assets/mobile_ui/assets/$asset") }
    }
    foreach ($needle in $requiredUiStrings + $requiredBridgeStrings) {
        if (-not $uiText.Contains($needle)) { throw "Required UI/bridge string not found in packaged JS: $needle" }
    }

    [pscustomobject]@{
        Apk = $ApkPath
        ApkSizeBytes = (Get-Item $ApkPath).Length
        RequiredEngineLibraries = $requiredLibraries.Count
        MobileUiAssets = $packagedAssets.Count
        ReachableMobileUiAssets = $neededAssets.Count
        InputControlProfiles = $profileEntries.Count
        Status = "OK"
    } | Format-List
} finally {
    $zip.Dispose()
}

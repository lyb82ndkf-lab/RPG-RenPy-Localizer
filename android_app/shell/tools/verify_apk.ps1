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

    $rpgMakerRuntimeEntry = "assets/rpgmaker/rpgrtl_runtime.js"
    if ($entryNames -notcontains $rpgMakerRuntimeEntry) {
        throw "Missing RPG Maker physical-save runtime in APK: $rpgMakerRuntimeEntry"
    }
    $rpgMakerRuntime = Read-ZipText $zip $rpgMakerRuntimeEntry

    $dashboardEntries = @(
        "assets/mtool/mtool_overlay.html",
        "assets/mtool/mtool_overlay.css",
        "assets/mtool/mtool_overlay.js"
    )
    foreach ($dashboardEntry in $dashboardEntries) {
        if ($entryNames -notcontains $dashboardEntry) {
            throw "Missing full-screen MTool dashboard asset in APK: $dashboardEntry"
        }
    }
    $dashboardHtml = Read-ZipText $zip "assets/mtool/mtool_overlay.html"
    $dashboardCss = Read-ZipText $zip "assets/mtool/mtool_overlay.css"
    $dashboardScript = Read-ZipText $zip "assets/mtool/mtool_overlay.js"
    if (-not $dashboardHtml.Contains("RPGRenPyLocalizer")) { throw "MTool dashboard brand is incorrect." }
    foreach ($forbidden in @("backdrop-filter", "box-shadow")) {
        if ($dashboardCss.Contains($forbidden)) { throw "MTool dashboard contains GPU-heavy CSS: $forbidden" }
    }
    foreach ($scrollMarker in @("touch-action:pan-y", "-webkit-overflow-scrolling:touch", "safe-area-inset-top", "safe-area-inset-right", "@media(orientation:portrait)")) {
        if (-not $dashboardCss.Replace(" ", "").Contains($scrollMarker)) { throw "MTool dashboard is missing touch/cutout marker: $scrollMarker" }
    }
    foreach ($touchShieldMarker in @("touchstart", "pointerdown", "mousedown", "stopPropagation")) {
        if (-not $dashboardScript.Contains($touchShieldMarker)) { throw "MTool dashboard touch shield is incomplete: $touchShieldMarker" }
    }
    foreach ($coverageMarker in @("pointer-events:auto", "min-width:100vw", "min-height:100vh")) {
        if (-not $dashboardCss.Replace(" ", "").Contains($coverageMarker)) { throw "MTool dashboard coverage is incomplete: $coverageMarker" }
    }
    foreach ($dashboardMarker in @("主页", "物品", "防具", "武器", "开关", "变量", "角色", "地图Ex", "按键设定")) {
        if (-not $dashboardScript.Contains($dashboardMarker)) {
            throw "MTool dashboard is incomplete; missing tab marker: $dashboardMarker"
        }
    }
    foreach ($needle in @("saveSaveData", "loadSaveData", "mvFileName", ".rmmzsave", "__RPGRTL_TRAINER")) {
        if (-not $rpgMakerRuntime.Contains($needle)) {
            throw "RPG Maker runtime is incomplete; missing marker: $needle"
        }
    }

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
            foreach ($m in [regex]::Matches($js, 'import\(`\./([^`]+\.(?:js|css))`\)')) {
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
        RpgMakerRuntime = "OK"
        MToolDashboard = "OK"
        RequiredEngineLibraries = $requiredLibraries.Count
        MobileUiAssets = $packagedAssets.Count
        ReachableMobileUiAssets = $neededAssets.Count
        InputControlProfiles = $profileEntries.Count
        Status = "OK"
    } | Format-List
} finally {
    $zip.Dispose()
}






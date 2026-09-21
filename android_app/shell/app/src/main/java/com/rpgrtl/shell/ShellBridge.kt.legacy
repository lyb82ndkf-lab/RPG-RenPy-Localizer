package com.rpgrtl.shell

import android.webkit.JavascriptInterface

class ShellBridge(private val activity: MainActivity) {
    @JavascriptInterface
    fun pickGameFolder() {
        activity.runOnUiThread {
            activity.pickGameFolder()
        }
    }

    @JavascriptInterface
    fun pickGameExe() {
        activity.runOnUiThread {
            activity.pickGameExe()
        }
    }

    @JavascriptInterface
    fun openOverlaySettings() {
        activity.runOnUiThread {
            activity.openOverlaySettings()
        }
    }

    @JavascriptInterface
    fun saveTouchControls(json: String) {
        activity.runOnUiThread {
            activity.saveTouchControls(json)
        }
    }

    @JavascriptInterface
    fun saveLaunchSettings(json: String): String {
        return activity.saveLaunchSettings(json)
    }

    @JavascriptInterface
    fun androidLaunchSettings(): String {
        return activity.androidLaunchSettings()
    }

    @JavascriptInterface
    fun scanSelectedGame() {
        activity.runOnUiThread {
            activity.scanSelectedGame()
        }
    }

    @JavascriptInterface
    fun scanSelectedGamePath(uri: String) {
        activity.runOnUiThread {
            activity.scanSelectedGamePath(uri)
        }
    }

    @JavascriptInterface
    fun selectGameFolder(uri: String): String {
        return activity.selectGameFolder(uri)
    }

    @JavascriptInterface
    fun selectGamePath(uri: String): String {
        return activity.selectGamePath(uri)
    }

    @JavascriptInterface
    fun checkGamePaths(requestJson: String): String {
        return activity.checkGamePaths(requestJson)
    }

    @JavascriptInterface
    fun androidGameLibrary(): String {
        return activity.androidGameLibrary()
    }

    @JavascriptInterface
    fun androidSaveGameLibrary(json: String): String {
        return activity.androidSaveGameLibrary(json)
    }

    @JavascriptInterface
    fun androidRemoveGame(key: String): String {
        return activity.androidRemoveGame(key)
    }

    @JavascriptInterface
    fun androidRefreshGameIcon(key: String): String {
        return activity.androidRefreshGameIcon(key)
    }

    @JavascriptInterface
    fun launchSelectedGame() {
        activity.runOnUiThread {
            activity.launchSelectedGame()
        }
    }

    @JavascriptInterface
    fun launchRenpyGame() {
        activity.runOnUiThread {
            activity.launchRenpyGame()
        }
    }

    @JavascriptInterface
    fun launchExeWithExternalRunner() {
        activity.runOnUiThread {
            activity.launchExeWithExternalRunner()
        }
    }

    @JavascriptInterface
    fun androidLaunchGame(backend: String): String {
        return activity.androidLaunchGame(backend)
    }

    @JavascriptInterface
    fun androidRuntimeLog(): String {
        return activity.androidRuntimeLog()
    }

    @JavascriptInterface
    fun clearRuntimeLog(): String {
        return activity.clearRuntimeLog()
    }

    @JavascriptInterface
    fun copyRuntimeLog(): String {
        return activity.copyRuntimeLog()
    }

    @JavascriptInterface
    fun toggleToolPage() {
        activity.runOnUiThread {
            activity.toggleToolPage()
        }
    }

    @JavascriptInterface
    fun returnToGame() {
        activity.runOnUiThread {
            activity.returnToGame()
        }
    }

    @JavascriptInterface
    fun androidTranslationEntries(limit: Int): String {
        return activity.androidTranslationEntries(limit)
    }

    @JavascriptInterface
    fun androidDataRecords(requestJson: String): String {
        return activity.androidDataRecords(requestJson)
    }

    @JavascriptInterface
    fun androidUpdateRecord(recordJson: String, newValue: String): String {
        return activity.androidUpdateRecord(recordJson, newValue)
    }

    @JavascriptInterface
    fun androidSaveTranslationEntries(requestJson: String): String {
        return activity.androidSaveTranslationEntries(requestJson)
    }

    @JavascriptInterface
    fun androidMaps(): String {
        return activity.androidMaps()
    }

    @JavascriptInterface
    fun androidMapDetail(mapId: Int): String {
        return activity.androidMapDetail(mapId)
    }

    @JavascriptInterface
    fun androidSaveSlots(): String {
        return activity.androidSaveSlots()
    }

    @JavascriptInterface
    fun androidCreateSaveBackup(): String {
        return activity.androidCreateSaveBackup()
    }

    @JavascriptInterface
    fun androidBackups(): String {
        return activity.androidBackups()
    }

    @JavascriptInterface
    fun androidGetSavePath(): String {
        return activity.androidGetSavePath()
    }

    @JavascriptInterface
    fun androidAiSettings(): String {
        return activity.androidAiSettings()
    }

    @JavascriptInterface
    fun saveAiSettings(json: String): String {
        return activity.saveAiSettings(json)
    }

    @JavascriptInterface
    fun androidAiTranslate(requestJson: String): String {
        return activity.androidAiTranslate(requestJson)
    }

    @JavascriptInterface
    fun androidRenpyLiveStatus(): String {
        return activity.androidRenpyLiveStatus()
    }

    @JavascriptInterface
    fun androidAiModels(settingsJson: String): String {
        return activity.androidAiModels(settingsJson)
    }

    @JavascriptInterface
    fun runtimeStatus(): String {
        return activity.runtimeStatus()
    }

    @JavascriptInterface
    fun runtimeCheat(action: String, value: String): String {
        return activity.runtimeCheat(action, value)
    }

    @JavascriptInterface
    fun androidRuntimeEval(script: String): String {
        return activity.androidRuntimeEval(script)
    }

    @JavascriptInterface
    fun androidToolbarAction(action: String): String {
        return activity.androidToolbarAction(action)
    }
}

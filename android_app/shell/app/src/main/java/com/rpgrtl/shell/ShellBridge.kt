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
    fun saveLaunchSettings(json: String) {
        activity.runOnUiThread {
            activity.saveLaunchSettings(json)
        }
    }

    @JavascriptInterface
    fun scanSelectedGame() {
        activity.runOnUiThread {
            activity.scanSelectedGame()
        }
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
    fun androidTranslationEntries(limit: Int): String {
        return activity.androidTranslationEntries(limit)
    }

    @JavascriptInterface
    fun androidDataRecords(category: String, limit: Int): String {
        return activity.androidDataRecords(category, limit)
    }

    @JavascriptInterface
    fun androidUpdateRecord(recordJson: String, newValue: String): String {
        return activity.androidUpdateRecord(recordJson, newValue)
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
}

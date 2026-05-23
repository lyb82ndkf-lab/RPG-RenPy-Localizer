package com.rpgrtl.shell

import android.webkit.JavascriptInterface
import android.util.Log

class GameErrorBridge(private val activity: MainActivity) {
    @JavascriptInterface
    fun androidJsError(json: String) {
        Log.e("GAME_JS", json)
    }
}

package com.rpgrtl.shell

import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient

class ShellWebViewClient(private val activity: MainActivity) : WebViewClient() {
    override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
        return false
    }

    override fun shouldInterceptRequest(
        view: WebView?,
        request: WebResourceRequest?
    ): WebResourceResponse? {
        val uri = request?.url ?: return null
        if (uri.scheme == "https" && uri.host == "rpgrtl.local" && uri.path?.startsWith("/game/") == true) {
            return activity.openGameAsset(uri.path!!.removePrefix("/game/"))
        }
        return null
    }

    override fun onPageFinished(view: WebView?, url: String?) {
        super.onPageFinished(view, url)
        if (url != null && url.contains("mobile_ui/index.html")) {
            activity.dispatchRestoredFolderIfAny()
            return
        }
        if (url == null || (!url.contains("rpgrtl_game_runtime") && !url.contains("rpgrtl.local/game"))) return
        val patch = """
            (function() {
              if (!window.StorageManager || window.__rpgrtlAndroidSaveFix) return;
              window.__rpgrtlAndroidSaveFix = true;
              var prefix = "RPGRenPyLocalizer_Save_";
              StorageManager.saveToLocalFile = function(savefileId, json) {
                localStorage.setItem(prefix + savefileId, json);
                return true;
              };
              StorageManager.loadFromLocalFile = function(savefileId) {
                return localStorage.getItem(prefix + savefileId);
              };
              StorageManager.exists = function(savefileId) {
                return localStorage.getItem(prefix + savefileId) !== null;
              };
              StorageManager.remove = function(savefileId) {
                localStorage.removeItem(prefix + savefileId);
              };
            })();
        """.trimIndent()
        view?.evaluateJavascript(patch, null)
        activity.reapplyGameOverlay()
    }
}

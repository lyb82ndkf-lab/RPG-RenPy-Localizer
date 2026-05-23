package com.rpgrtl.shell

import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.RenderProcessGoneDetail
import android.util.Log

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
        Log.d("PERF", "Page finished: ${url ?: "unknown"}")
        injectFpsMonitor(view)
        if (url != null && url.contains("mobile_ui/index.html")) {
            return
        }
        if (url == null || (!url.contains("rpgrtl_game_runtime") && !url.contains("rpgrtl.local/game"))) return
        activity.injectGameCompatibilityPatch(view)
        activity.injectGameErrorCollector(view)
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
        activity.injectCheatScript()
        activity.reapplyGameOverlay()
    }

    override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
        Log.e("PERF", "WebView render process gone, didCrash=${detail.didCrash()}")
        activity.onWebViewRenderProcessGone(view, detail.didCrash())
        return true
    }

    private fun injectFpsMonitor(view: WebView?) {
        val script = """
            (function(){
              if (window.__rpgrtlFpsMonitor) return;
              window.__rpgrtlFpsMonitor = true;
              var frames = 0;
              var last = performance.now();
              function tick(){
                frames++;
                var now = performance.now();
                if (now - last >= 1000) {
                  var fps = Math.round(frames * 1000 / (now - last));
                  if (fps < 30) console.warn('[PERF] Low FPS: ' + fps);
                  frames = 0;
                  last = now;
                }
                requestAnimationFrame(tick);
              }
              requestAnimationFrame(tick);
            })();
        """.trimIndent()
        view?.evaluateJavascript(script, null)
    }
}

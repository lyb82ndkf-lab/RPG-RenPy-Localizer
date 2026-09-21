package com.rpgrtl.shell.rpgmaker

import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ActivityInfo
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.JsResult
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.core.view.ViewCompat
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import com.rpgrtl.shell.ShellLog
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.File

class RpgMakerWebViewActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_INDEX_PATH = "extra_index_path"
        const val EXTRA_GAME_DIR = "extra_game_dir"
        const val EXTRA_GAME_TITLE = "extra_game_title"
        private const val PREFS_NAME = "rpgmaker_ingame_controls"
        private const val PREF_GAMEPAD_VISIBLE = "gamepad_visible"
        private const val PREF_GAMEPAD_ALPHA = "gamepad_alpha"
    }

    private var webView: WebView? = null
    private var gameDir: File? = null
    private var webRoot: File? = null
    private var reloadReceiver: BroadcastReceiver? = null
    private var virtualGamepad: VirtualGamepadView? = null
    private var floatingButton: InGameFloatingButton? = null
    private var dashboardVisible = false
    private lateinit var gameTitle: String
    private val runtimeScript: String by lazy {
        assets.open("rpgmaker/rpgrtl_runtime.js").bufferedReader(Charsets.UTF_8).use { it.readText() }
    }
    private val dashboardHtml: String by lazy {
        assets.open("mtool/mtool_overlay.html").bufferedReader(Charsets.UTF_8).use { it.readText() }
    }
    private val dashboardCss: String by lazy {
        assets.open("mtool/mtool_overlay.css").bufferedReader(Charsets.UTF_8).use { it.readText() }
    }
    private val dashboardScript: String by lazy {
        assets.open("mtool/mtool_overlay.js").bufferedReader(Charsets.UTF_8).use { it.readText() }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ShellLog.installCrashLogger(this)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE

        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            window.attributes = window.attributes.apply {
                layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }
        hideSystemUI()

        val indexPath = intent.getStringExtra(EXTRA_INDEX_PATH).orEmpty()
        val gameDirPath = intent.getStringExtra(EXTRA_GAME_DIR).orEmpty()
        gameTitle = intent.getStringExtra(EXTRA_GAME_TITLE).orEmpty().ifBlank { "RPG Maker Game" }

        val indexFile = File(indexPath)
        if (!indexFile.exists() || !indexFile.isFile) {
            Toast.makeText(this, "未找到游戏启动页面: $indexPath", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        val dir = if (gameDirPath.isNotBlank()) File(gameDirPath) else indexFile.parentFile ?: File(".")
        val rootDir = indexFile.parentFile ?: dir
        gameDir = dir
        webRoot = rootDir

        val root = FrameLayout(this).apply { setBackgroundColor(Color.BLACK) }
        val wv = WebView(this).apply {
            setBackgroundColor(Color.BLACK)
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        }
        webView = wv
        root.addView(wv)
        setContentView(root)

        configureWebView(wv, dir, rootDir)
        addGameOverlays(root, wv)
        installSafeAreaInsets(root)
        registerReloadReceiver()
        broadcastGameState(true, dir)

        wv.loadUrl(Uri.fromFile(indexFile).toString())
        Toast.makeText(this, "正在通过原生 Web 引擎启动：$gameTitle", Toast.LENGTH_SHORT).show()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView(wv: WebView, dir: File, rootDir: File) {
        wv.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            allowFileAccessFromFileURLs = true
            allowUniversalAccessFromFileURLs = true
            mediaPlaybackRequiresUserGesture = false
            cacheMode = WebSettings.LOAD_NO_CACHE
            loadWithOverviewMode = true
            useWideViewPort = true
            displayZoomControls = false
            builtInZoomControls = false
        }

        wv.addJavascriptInterface(RpgMakerNativeBridge(this, dir, rootDir), "RPGRTLBridge")
        wv.webChromeClient = createChromeClient()
        wv.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean = false

            override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
                return request?.url?.let(::interceptManagerScript) ?: super.shouldInterceptRequest(view, request)
            }

            @Deprecated("Deprecated in Android")
            override fun shouldInterceptRequest(view: WebView?, url: String?): WebResourceResponse? {
                return url?.let { runCatching { Uri.parse(it) }.getOrNull() }
                    ?.let(::interceptManagerScript)
                    ?: super.shouldInterceptRequest(view, url)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                // Standard engine files receive this runtime before boot through interception.
                // Re-evaluate here as a fallback for renamed/bundled engine distributions.
                injectRuntime(view)
                injectTextHook(view)
                injectDashboard(view)
            }
        }
    }

    private fun createChromeClient(): WebChromeClient = object : WebChromeClient() {
        override fun onConsoleMessage(consoleMessage: ConsoleMessage?): Boolean {
            consoleMessage?.let {
                ShellLog.info(this@RpgMakerWebViewActivity, "RPG WebView Console [${it.messageLevel()}]: ${it.message()}")
            }
            return super.onConsoleMessage(consoleMessage)
        }

        override fun onJsAlert(view: WebView?, url: String?, message: String?, result: JsResult?): Boolean {
            AlertDialog.Builder(this@RpgMakerWebViewActivity)
                .setTitle(gameTitle)
                .setMessage(message.orEmpty())
                .setPositiveButton("确定") { _, _ -> result?.confirm() }
                .setOnCancelListener { result?.cancel() }
                .show()
            return true
        }

        override fun onJsConfirm(view: WebView?, url: String?, message: String?, result: JsResult?): Boolean {
            AlertDialog.Builder(this@RpgMakerWebViewActivity)
                .setTitle(gameTitle)
                .setMessage(message.orEmpty())
                .setPositiveButton("确定") { _, _ -> result?.confirm() }
                .setNegativeButton("取消") { _, _ -> result?.cancel() }
                .setOnCancelListener { result?.cancel() }
                .show()
            return true
        }
    }

    private fun interceptManagerScript(uri: Uri): WebResourceResponse? {
        if (uri.scheme != "file") return null
        val name = uri.lastPathSegment?.lowercase().orEmpty()
        if (name != "rpg_managers.js" && name != "rmmz_managers.js") return null

        val scriptFile = uri.path?.let(::File) ?: return null
        val allowed = listOfNotNull(gameDir, webRoot).mapNotNull { runCatching { it.canonicalFile }.getOrNull() }
        val canonical = runCatching { scriptFile.canonicalFile }.getOrNull() ?: return null
        if (allowed.none { root -> canonical.path == root.path || canonical.path.startsWith(root.path + File.separator) }) {
            return null
        }

        return runCatching {
            val source = canonical.readText(Charsets.UTF_8)
            val patched = "$source\n;/* RPGRenPy Android physical-save runtime */\n$runtimeScript\n"
            WebResourceResponse(
                "application/javascript",
                "UTF-8",
                ByteArrayInputStream(patched.toByteArray(Charsets.UTF_8))
            )
        }.onFailure {
            ShellLog.error(this, "Unable to inject RPG Maker manager runtime: ${canonical.absolutePath}", it)
        }.getOrNull()
    }

    private fun addGameOverlays(root: FrameLayout, wv: WebView) {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val gamepadVisible = prefs.getBoolean(PREF_GAMEPAD_VISIBLE, true)
        val gamepadAlpha = prefs.getFloat(PREF_GAMEPAD_ALPHA, 0.58f)

        virtualGamepad = VirtualGamepadView(this, wv).also { gamepad ->
            gamepad.layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
            val savedProfile = prefs.getString("gamepad_profile_json", "").orEmpty()
            if (savedProfile.isNotBlank()) gamepad.applyProfile(savedProfile) else gamepad.setControlsAlpha(gamepadAlpha)
            gamepad.setGamepadVisible(gamepadVisible)
            root.addView(gamepad)
        }

        floatingButton = InGameFloatingButton(this) { toggleDashboard() }.also { button ->
            root.addView(button, FrameLayout.LayoutParams(dp(50), dp(50), Gravity.TOP or Gravity.END).apply {
                topMargin = dp(14)
                marginEnd = dp(14)
            })
            button.post { button.resetPosition() }
        }
    }

    private fun installSafeAreaInsets(root: FrameLayout) {
        ViewCompat.setOnApplyWindowInsetsListener(root) { _, windowInsets ->
            val safe = windowInsets.getInsetsIgnoringVisibility(
                WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout()
            )
            virtualGamepad?.setSafeInsets(safe.left, safe.top, safe.right, safe.bottom)
            floatingButton?.let { button ->
                val params = button.layoutParams as? FrameLayout.LayoutParams ?: return@let
                params.topMargin = maxOf(dp(10), safe.top + dp(6))
                params.marginEnd = maxOf(dp(10), safe.right + dp(6))
                button.layoutParams = params
                button.resetPosition()
            }
            windowInsets
        }
        ViewCompat.requestApplyInsets(root)
    }

    private fun injectDashboard(view: WebView?) {
        val install = """
            (function() {
                var viewport = document.querySelector('meta[name="viewport"]');
                if (!viewport) {
                    viewport = document.createElement('meta');
                    viewport.name = 'viewport';
                    viewport.content = 'width=device-width,initial-scale=1,viewport-fit=cover';
                    document.head.appendChild(viewport);
                } else if (viewport.content.indexOf('viewport-fit=cover') < 0) {
                    viewport.content += ',viewport-fit=cover';
                }
            })();
            $dashboardScript
            if (window.__RPGRTL_MTOOL) {
                window.__RPGRTL_MTOOL.install(${JSONObject.quote(dashboardHtml)}, ${JSONObject.quote(dashboardCss)});
            }
        """.trimIndent()
        view?.evaluateJavascript(install, null)
    }

    private fun toggleDashboard() {
        // Native overlays are siblings above the WebView. Hide them and promote the
        // WebView before opening the DOM dashboard, otherwise right-side gamepad
        // buttons can intercept touches before JavaScript ever sees them.
        onDashboardVisibilityChanged(true)
        webView?.evaluateJavascript(
            "if(window.__RPGRTL_MTOOL){window.__RPGRTL_MTOOL.open();true}else{false}"
        ) { result ->
            if (result != "true") {
                onDashboardVisibilityChanged(false)
                Toast.makeText(this, "游戏控制台尚未加载完成，请稍后重试", Toast.LENGTH_SHORT).show()
            }
        }
    }

    internal fun onDashboardVisibilityChanged(visible: Boolean) {
        dashboardVisible = visible
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        if (visible) {
            virtualGamepad?.releaseAllKeys()
            virtualGamepad?.visibility = View.GONE
            floatingButton?.visibility = View.GONE
            webView?.bringToFront()
            webView?.requestFocus()
            ShellLog.info(this, "RPG dashboard opened: WebView promoted above native controls")
        } else {
            reapplySavedGamepadProfile()
            virtualGamepad?.setGamepadVisible(prefs.getBoolean(PREF_GAMEPAD_VISIBLE, true))
            virtualGamepad?.bringToFront()
            floatingButton?.visibility = View.VISIBLE
            floatingButton?.bringToFront()
            ShellLog.info(this, "RPG dashboard closed: native controls restored")
        }
    }

    private fun reapplySavedGamepadProfile() {
        val savedProfile = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString("gamepad_profile_json", "").orEmpty()
        if (savedProfile.isNotBlank()) virtualGamepad?.applyProfile(savedProfile)
    }

    internal fun applyGamepadProfile(json: String) {
        virtualGamepad?.applyProfile(json)
        virtualGamepad?.requestLayout()
        Toast.makeText(this, "虚拟按键位置、大小与透明度已应用", Toast.LENGTH_SHORT).show()
    }

    internal fun vibrateFromDashboard(durationMs: Int, strength: Int) {
        virtualGamepad?.vibrate(durationMs.coerceIn(0, 250), strength.coerceIn(1, 255))
    }

    private fun saveAndExit() {
        webView?.evaluateJavascript(
            "window.__RPGRTL_TRAINER ? window.__RPGRTL_TRAINER.saveAndExit() : '游戏工具尚未就绪'",
            null
        )
    }
    private fun registerReloadReceiver() {
        reloadReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                webView?.evaluateJavascript(
                    "if(window.__rpgrtl_reloadTranslations){window.__rpgrtl_reloadTranslations();}",
                    null
                )
                Toast.makeText(this@RpgMakerWebViewActivity, "RPG Maker 翻译已热重载注入", Toast.LENGTH_SHORT).show()
            }
        }
        LocalBroadcastManager.getInstance(this).registerReceiver(
            reloadReceiver!!,
            IntentFilter("com.rpgrtl.RELOAD_TRANSLATIONS")
        )
    }

    private fun broadcastGameState(running: Boolean, dir: File? = null) {
        LocalBroadcastManager.getInstance(this).sendBroadcast(
            Intent("com.rpgrtl.GAME_STATE").apply {
                putExtra("running", running)
                if (dir != null) {
                    putExtra("game_dir", dir.absolutePath)
                    putExtra("engine", "RPG_MAKER_MV_MZ")
                    putExtra("game_title", gameTitle)
                }
            }
        )
    }

    private fun injectRuntime(view: WebView?) {
        view?.evaluateJavascript(runtimeScript, null)
    }

    private fun injectTextHook(view: WebView?) {
        val script = """
            (function() {
                if (window.__RPGRTL_INJECTED) {
                    if (window.__rpgrtl_reloadTranslations) window.__rpgrtl_reloadTranslations();
                    return;
                }
                window.__RPGRTL_INJECTED = true;
                try {
                    window.__RPGRTL_TRANS_MAP = window.RPGRTLBridge
                        ? JSON.parse(window.RPGRTLBridge.getTranslationMap() || "{}") : {};
                } catch(e) { window.__RPGRTL_TRANS_MAP = {}; }

                window.__rpgrtl_reloadTranslations = function() {
                    try {
                        if (window.RPGRTLBridge) {
                            window.__RPGRTL_TRANS_MAP = JSON.parse(window.RPGRTLBridge.getTranslationMap() || "{}");
                        }
                    } catch(e) {}
                };

                function translate(text) {
                    if (!text || typeof text !== 'string') return text;
                    var map = window.__RPGRTL_TRANS_MAP;
                    if (!map) return text;
                    var trimmed = text.trim();
                    return map[trimmed] ? text.replace(trimmed, map[trimmed]) : text;
                }

                if (typeof Bitmap !== 'undefined' && Bitmap.prototype && Bitmap.prototype.drawText) {
                    var originalDrawText = Bitmap.prototype.drawText;
                    Bitmap.prototype.drawText = function(text, x, y, maxWidth, lineHeight, align) {
                        return originalDrawText.call(this, translate(text), x, y, maxWidth, lineHeight, align);
                    };
                }
                if (typeof Window_Base !== 'undefined' && Window_Base.prototype && Window_Base.prototype.drawTextEx) {
                    var originalDrawTextEx = Window_Base.prototype.drawTextEx;
                    Window_Base.prototype.drawTextEx = function(text, x, y) {
                        return originalDrawTextEx.call(this, translate(text), x, y);
                    };
                }
            })();
        """.trimIndent()
        view?.evaluateJavascript(script, null)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density + 0.5f).toInt()

    private fun hideSystemUI() {
        val controller = WindowCompat.getInsetsController(window, window.decorView)
        controller.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        controller.hide(WindowInsetsCompat.Type.systemBars())
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemUI()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (dashboardVisible) {
                webView?.evaluateJavascript("if(window.__RPGRTL_MTOOL){window.__RPGRTL_MTOOL.close();}", null)
                return true
            }
            AlertDialog.Builder(this)
                .setTitle("退出游戏")
                .setMessage("确定要退出当前游戏吗？未保存的进度会丢失。")
                .setPositiveButton("保存并退出") { _, _ -> saveAndExit() }
                .setNeutralButton("直接退出") { _, _ -> finish() }
                .setNegativeButton("继续游戏", null)
                .show()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onPause() {
        virtualGamepad?.releaseAllKeys()
        webView?.onPause()
        super.onPause()
    }

    override fun onResume() {
        super.onResume()
        webView?.onResume()
        hideSystemUI()
    }

    override fun onDestroy() {
        reloadReceiver?.let { LocalBroadcastManager.getInstance(this).unregisterReceiver(it) }
        reloadReceiver = null
        broadcastGameState(false)
        virtualGamepad?.releaseAllKeys()
        virtualGamepad = null
        floatingButton = null

        webView?.let { wv ->
            wv.removeJavascriptInterface("RPGRTLBridge")
            wv.stopLoading()
            wv.loadUrl("about:blank")
            wv.clearHistory()
            wv.removeAllViews()
            wv.destroy()
        }
        webView = null
        super.onDestroy()
    }
}





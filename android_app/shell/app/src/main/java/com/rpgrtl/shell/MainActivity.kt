package com.rpgrtl.shell

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.os.Build
import android.provider.Settings
import android.content.ComponentCallbacks2
import android.util.Log
import android.view.KeyEvent
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.LinearLayout
import android.widget.FrameLayout
import android.widget.TextView
import android.webkit.WebSettings
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebChromeClient
import android.webkit.ConsoleMessage
import androidx.documentfile.provider.DocumentFile
import com.rpgrtl.shell.databinding.ActivityMainBinding
import com.rpgrtl.shell.wine.WineEngineBridge
import com.rpgrtl.shell.wine.WineDisplayActivity
import com.rpgrtl.shell.wine.WineSaveService
import java.io.File
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.Callable
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : Activity() {
    private lateinit var binding: ActivityMainBinding
    private val pickGameFolderRequest = 7101
    private val pickGameExeRequest = 7102
    private var lastTreeUri: Uri? = null
    private var lastExeUri: Uri? = null
    private var gameTreeRoot: DocumentFile? = null
    private var gameVirtualBase = ""
    private var lastGameUrl = ""
    private var gameViewActive = false
    private var cachedEntryPath = ""
    private var gamePreloaded = false
    private var cheatScriptSource = ""
    private val gameAssetCache = mutableMapOf<String, DocumentFile?>()
    private val gameDirectoryCache = mutableMapOf<String, List<DocumentFile>>()
    private val gamePathIndex = mutableMapOf<String, String>()
    @Volatile private var gameFileIndex: Map<String, DocumentFile> = emptyMap()
    @Volatile private var runSessionId = 0
    private val apiCache = ConcurrentHashMap<String, String>()
    private val apiPool = Executors.newFixedThreadPool(2)
    private var createStartMs = 0L
    private val touchButtonViews = mutableListOf<View>()
    private var gameToolbarView: LinearLayout? = null
    private var gameToolbarExpanded = false
    private var gameLoadingOverlay: LinearLayout? = null
    private var touchBlockerView: View? = null
    private var touchBlocked = false
    private var externalSourceApp = ""
    private var externalContainerId = -1
    private var externalContainerName = ""
    private var externalGameTitle = ""
    private var externalGamePath = ""
    private var externalTargetPage = ""
    private var toolPageGameMode = false

    override fun onCreate(savedInstanceState: Bundle?) {
        createStartMs = System.nanoTime()
        setTheme(R.style.Theme_RPGRenPyLocalizer)
        super.onCreate(savedInstanceState)
        ShellLog.installCrashLogger(this)
        ShellLog.info(this, "MainActivity onCreate ${appVersionLabel()}")
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        consumeExternalLaunchIntent(intent)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        applyToolPageSystemUi()
        setupWebView(binding.webView, exposeBridge = true)
        setupWebView(binding.gameWebView, exposeBridge = false)
        binding.gameWebView.addJavascriptInterface(GameErrorBridge(this), "RPGRenPyGameBridge")
        binding.toolButton.setOnClickListener {
            toggleToolPage()
        }
        restoreLastTreeUri()
        loadToolPage()
        Log.d("PERF", "onCreate -> loadToolPage: ${(System.nanoTime() - createStartMs) / 1_000_000}ms")
        requestStartupPermissions()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        consumeExternalLaunchIntent(intent)
        if (externalSourceApp == "rpgtl_wine") {
            toolPageGameMode = true
            requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
            loadToolPage(fromGame = true)
        }
        if (!externalGamePath.isBlank() || externalContainerId >= 0 || externalContainerName.isNotBlank()) {
            notifyWeb("Connected from Winlator: ${externalGameTitle.ifBlank { externalContainerName.ifBlank { "game" } }}")
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) applySystemUiForCurrentMode()
    }

    override fun onResume() {
        super.onResume()
        applySystemUiForCurrentMode()
        binding.webView.onResume()
        binding.webView.resumeTimers()
        binding.gameWebView.onResume()
        binding.gameWebView.resumeTimers()
        reflowWebViewSoon()
    }

    override fun onPause() {
        binding.webView.onPause()
        binding.webView.pauseTimers()
        binding.gameWebView.onPause()
        binding.gameWebView.pauseTimers()
        super.onPause()
    }

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        if (level >= ComponentCallbacks2.TRIM_MEMORY_MODERATE) {
            binding.webView.clearCache(true)
            binding.gameWebView.clearCache(true)
            apiCache.clear()
            gameAssetCache.clear()
            gameDirectoryCache.clear()
            Log.d("PERF", "Trim memory level=$level, cleared WebView/API caches")
        }
        if (level >= ComponentCallbacks2.TRIM_MEMORY_COMPLETE) {
            if (gameViewActive) binding.webView.onPause() else binding.gameWebView.onPause()
        }
    }

    private fun applySystemUiForCurrentMode() {
        if (gameViewActive) enterImmersiveMode() else applyToolPageSystemUi()
    }

    /** Tool pages keep status bar visible so notch area is not a black void. */
    private fun applyToolPageSystemUi() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(true)
            window.insetsController?.show(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        }
        window.statusBarColor = 0xFF0B0F16.toInt()
        window.navigationBarColor = 0xFF0B0F16.toInt()
    }

    private fun enterImmersiveMode() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.let { controller ->
                controller.hide(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
                controller.systemBarsBehavior =
                    WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    or View.SYSTEM_UI_FLAG_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                )
        }
    }

    private fun requestStartupPermissions() {
        if (!Settings.canDrawOverlays(this)) notifyWeb("HUD uses in-game overlay; floating-window permission is optional.")
    }

    private fun consumeExternalLaunchIntent(intent: Intent?) {
        if (intent == null) return
        externalSourceApp = intent.getStringExtra("source_app") ?: externalSourceApp
        externalContainerId = intent.getIntExtra("container_id", externalContainerId)
        externalContainerName = intent.getStringExtra("container_name") ?: externalContainerName
        externalGameTitle = intent.getStringExtra("game_title") ?: externalGameTitle
        externalGamePath = intent.getStringExtra("game_path") ?: externalGamePath
        externalTargetPage = intent.getStringExtra("target_page") ?: externalTargetPage
        if (externalSourceApp == "rpgtl_wine") {
            toolPageGameMode = true
            requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        }
        val extras = JSONObject().apply {
            put("source_app", externalSourceApp)
            put("container_id", externalContainerId)
            put("container_name", externalContainerName)
            put("game_title", externalGameTitle)
            put("game_path", externalGamePath)
            put("target_page", externalTargetPage)
            put("mode", if (toolPageGameMode) "game" else "normal")
            put("game_mode", if (toolPageGameMode) "in_game" else "normal")
        }
        getPreferences(Context.MODE_PRIVATE)
            .edit()
            .putString("external_launch_context", extras.toString())
            .apply()
    }

    fun returnToGame() {
        if (externalSourceApp == "rpgtl_wine") {
            val intent = Intent(this, WineDisplayActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            }
            startActivity(intent)
            return
        }
        if (lastGameUrl.isNotBlank()) {
            showGamePage()
            return
        }
        toggleToolPage()
    }
    private fun setupWebView(webView: WebView, exposeBridge: Boolean) {
        with(webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            allowFileAccessFromFileURLs = true
            allowUniversalAccessFromFileURLs = true
            cacheMode = WebSettings.LOAD_DEFAULT
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                offscreenPreRaster = true
            }
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            mediaPlaybackRequiresUserGesture = false
            javaScriptCanOpenWindowsAutomatically = true
            loadsImagesAutomatically = true
            blockNetworkImage = false
            useWideViewPort = false
            loadWithOverviewMode = false
            textZoom = 100
            setSupportMultipleWindows(false)
            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false
        }
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null)
        webView.overScrollMode = View.OVER_SCROLL_NEVER
        webView.isHorizontalScrollBarEnabled = false
        webView.isVerticalScrollBarEnabled = false
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, true)
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(consoleMessage: ConsoleMessage): Boolean {
                val message = consoleMessage.message()
                if (message.contains("[PERF]")) Log.d("PERF", message)
                return super.onConsoleMessage(consoleMessage)
            }
        }
        webView.webViewClient = ShellWebViewClient(this)
        if (exposeBridge) webView.addJavascriptInterface(ShellBridge(this), "RPGRenPyShell")
        webView.isFocusable = true
        webView.isFocusableInTouchMode = true
        webView.requestFocus()
        webView.post {
            webView.evaluateJavascript(
                "document.body&&document.body.style&&(document.body.style.webkitTransform='translateZ(0)',document.body.style.transform='translateZ(0)');",
                null
            )
        }
    }

    private fun loadToolPage(fromGame: Boolean = false) {
        val hadRunningGame = fromGame || gameViewActive || lastGameUrl.isNotBlank() || externalSourceApp == "rpgtl_wine"
        gameViewActive = false
        toolPageGameMode = hadRunningGame && (fromGame || externalSourceApp == "rpgtl_wine")
        requestedOrientation = if (toolPageGameMode) {
            ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        } else {
            ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        }
        setGameTouchBlocked(false)
        hideGameLoadingOverlay(0)
        binding.gameWebView.visibility = View.INVISIBLE
        binding.webView.visibility = View.VISIBLE
        if (binding.webView.url.isNullOrBlank()) {
            binding.webView.loadUrl("file:///android_asset/mobile_ui/index.html")
        }
        pushToolModeContext()
        if (toolPageGameMode) {
            binding.webView.postDelayed({
                binding.webView.evaluateJavascript("window.onAndroidOpenToolPage&&window.onAndroidOpenToolPage('/cheats')", null)
            }, 120)
        } else {
            pushExternalLaunchContext()
        }
        reflowWebViewSoon()
        applySystemUiForCurrentMode()
        if (!toolPageGameMode) binding.webView.postDelayed({ preloadGameIfReady() }, 3000)
    }

    private fun showGamePage() {
        if (lastGameUrl.isBlank()) {
            loadToolPage(false)
            return
        }
        toolPageGameMode = false
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        gameViewActive = true
        applySystemUiForCurrentMode()
        updateToolButton()
        showGameLoadingOverlay("Restoring game view...")
        binding.webView.visibility = View.GONE
        binding.gameWebView.visibility = View.VISIBLE
        if (binding.gameWebView.url.isNullOrBlank()) {
            binding.gameWebView.loadUrl(lastGameUrl)
        }
        binding.gameWebView.onResume()
        binding.gameWebView.resumeTimers()
        reflowWebViewSoon()
        binding.gameWebView.postDelayed({ if (gameViewActive) applyTouchControls() }, 350)
        binding.gameWebView.postDelayed({ if (gameViewActive) applyTouchControls() }, 1200)
        binding.gameWebView.postDelayed({ injectCheatScript() }, 900)
        binding.gameWebView.postDelayed({ if (gameViewActive) showGameToolbar() }, 400)
    }

    private fun preloadGameIfReady() {
        if (gameViewActive || gamePreloaded || lastGameUrl.isBlank()) return
        if (!binding.gameWebView.url.isNullOrBlank()) {
            gamePreloaded = true
            return
        }
        gamePreloaded = true
        applyLaunchSettings()
        binding.gameWebView.visibility = View.INVISIBLE
        binding.gameWebView.loadUrl(lastGameUrl)
        Log.d("PERF", "Preloading game WebView: $lastGameUrl")
    }

    fun toggleToolPage() {
        if (gameViewActive) {
            loadToolPage(true)
        } else {
            showGamePage()
        }
    }

    fun showGameLoadingOverlay(message: String) {
        runOnUiThread {
            hideGameLoadingOverlay(0)
            val panel = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = android.view.Gravity.CENTER
                setPadding(dp(22f), dp(18f), dp(22f), dp(18f))
                background = android.graphics.drawable.GradientDrawable().apply {
                    shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                    cornerRadius = dp(18f).toFloat()
                    setColor(0xEE101722.toInt())
                    setStroke(dp(1f), 0x6655D6FF)
                }
                elevation = dp(14f).toFloat()
            }
            val progress = android.widget.ProgressBar(this).apply {
                isIndeterminate = true
            }
            val title = TextView(this).apply {
                text = "游戏正在启动"
                textSize = 16f
                setTextColor(Color.WHITE)
                gravity = android.view.Gravity.CENTER
                setPadding(0, dp(10f), 0, dp(4f))
                typeface = android.graphics.Typeface.DEFAULT_BOLD
            }
            val body = TextView(this).apply {
                text = message
                textSize = 12f
                setTextColor(0xFFB7C0CE.toInt())
                gravity = android.view.Gravity.CENTER
                maxLines = 3
            }
            panel.addView(progress, LinearLayout.LayoutParams(dp(36f), dp(36f)))
            panel.addView(title, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
            panel.addView(body, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
            gameLoadingOverlay = panel
            binding.root.addView(
                panel,
                FrameLayout.LayoutParams(dp(280f), FrameLayout.LayoutParams.WRAP_CONTENT).apply {
                    gravity = android.view.Gravity.CENTER
                }
            )
            panel.bringToFront()
            binding.toolButton.bringToFront()
        }
    }

    fun hideGameLoadingOverlay(delayMs: Long = 600L) {
        runOnUiThread {
            val overlay = gameLoadingOverlay ?: return@runOnUiThread
            val remove = Runnable {
                if (gameLoadingOverlay === overlay) {
                    binding.root.removeView(overlay)
                    gameLoadingOverlay = null
                }
            }
            if (delayMs <= 0) remove.run() else overlay.postDelayed(remove, delayMs)
        }
    }

    private fun showGameToolbar() {
        if (gameToolbarView == null) {
            gameToolbarView = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(0, 0, 0, 0)
            }
            binding.root.addView(
                gameToolbarView,
                FrameLayout.LayoutParams(dp(44f), FrameLayout.LayoutParams.WRAP_CONTENT).apply {
                    gravity = android.view.Gravity.START or android.view.Gravity.CENTER_VERTICAL
                }
            )
        }
        renderGameToolbar(false)
        gameToolbarView?.visibility = View.VISIBLE
        gameToolbarView?.bringToFront()
        binding.toolButton.bringToFront()
    }

    private fun removeGameToolbar() {
        gameToolbarView?.let { binding.root.removeView(it) }
        gameToolbarView = null
        gameToolbarExpanded = false
    }

    private fun renderGameToolbar(expanded: Boolean = gameToolbarExpanded) {
        val toolbar = gameToolbarView ?: return
        gameToolbarExpanded = expanded
        toolbar.removeAllViews()
        toolbar.addView(toolbarButton(if (expanded) "<" else "Menu", if (expanded) "Collapse" else "Game tools") {
            renderGameToolbar(!gameToolbarExpanded)
        })
        if (!expanded) return
        toolbar.addView(toolbarButton(if (touchBlocked) "On" else "Off", if (touchBlocked) "Enable touch" else "Disable touch", touchBlocked) { toolbarAction("touchToggle") })
        toolbar.addView(toolbarButton("Key", "Keyboard") { toolbarAction("keyboard") })
        toolbar.addView(toolbarButton("X", "Open panel") { toolbarAction("close") })
        toolbar.postDelayed({
            if (gameToolbarExpanded) renderGameToolbar(false)
        }, 10_000)
    }

    private fun toolbarButton(icon: String, label: String, active: Boolean = false, action: () -> Unit): TextView {
        return TextView(this).apply {
            text = icon
            contentDescription = label
            textSize = if (label == "Game tools") 13f else 12f
            gravity = android.view.Gravity.CENTER
            setTextColor(if (active) 0xFFFFD2D2.toInt() else 0xFFEAF4FF.toInt())
            background = android.graphics.drawable.GradientDrawable().apply {
                shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                cornerRadii = floatArrayOf(0f, 0f, dp(10f).toFloat(), dp(10f).toFloat(), dp(10f).toFloat(), dp(10f).toFloat(), 0f, 0f)
                setColor(if (active) 0xCC7F1D1D.toInt() else 0x99101B2B.toInt())
                setStroke(dp(1f), if (active) 0x88FF8A8A.toInt() else 0x6655D6FF)
            }
            alpha = if (label == "Game tools") 0.78f else 0.9f
            setOnClickListener {
                action()
                if (label != "Collapse" && label != "Game tools") {
                    gameToolbarView?.postDelayed({ if (gameToolbarExpanded) renderGameToolbar(false) }, 1500)
                }
            }
            layoutParams = LinearLayout.LayoutParams(dp(36f), dp(36f)).apply {
                bottomMargin = dp(4f)
            }
        }
    }

    private fun toolbarAction(action: String) {
        when (action) {
            "rotate" -> toggleOrientation()
            "touchToggle" -> setGameTouchBlocked(!touchBlocked)
            "keyboard" -> showGameKeyboard()
            "close" -> loadToolPage(true)
        }
    }

    fun androidToolbarAction(action: String): String {
        runOnUiThread { toolbarAction(action) }
        return JSONObject().put("ok", true).put("action", action).toString()
    }

    private fun toggleOrientation() {
        val current = resources.configuration.orientation
        requestedOrientation = if (current == Configuration.ORIENTATION_LANDSCAPE) {
            ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        } else {
            ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        }
        binding.gameWebView.postDelayed({
            injectGameCompatibilityPatch(binding.gameWebView)
            injectCheatScript()
            applyTouchControls()
            showGameToolbar()
            binding.gameWebView.evaluateJavascript("window.dispatchEvent(new Event('resize'));", null)
        }, 450)
    }

    private fun setGameTouchBlocked(blocked: Boolean) {
        touchBlocked = blocked
        if (touchBlockerView == null) {
            touchBlockerView = View(this).apply {
                setBackgroundColor(Color.TRANSPARENT)
                isClickable = true
                isFocusable = false
                setOnTouchListener { _, _ -> true }
            }
            binding.root.addView(
                touchBlockerView,
                FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT)
            )
        }
        touchBlockerView?.visibility = if (blocked && gameViewActive) View.VISIBLE else View.GONE
        touchBlockerView?.bringToFront()
        touchButtonViews.forEach { it.bringToFront() }
        gameToolbarView?.bringToFront()
        binding.toolButton.bringToFront()
        if (gameToolbarView != null) renderGameToolbar(gameToolbarExpanded)
    }

    private fun showGameKeyboard() {
        val script = """
            (function(){
              var input = document.getElementById('rpgrtl-ime-proxy');
              if (!input) {
                input = document.createElement('input');
                input.id = 'rpgrtl-ime-proxy';
                input.type = 'text';
                input.autocomplete = 'off';
                input.style.cssText = 'position:fixed;left:-2000px;top:-2000px;width:1px;height:1px;opacity:0;z-index:-1;';
                input.addEventListener('input', function(){
                  var text = input.value || '';
                  if (!text) return;
                  var ch = text.charAt(text.length - 1);
                  var code = ch.charCodeAt(0);
                  var down = new KeyboardEvent('keydown', {key:ch,keyCode:code,which:code,bubbles:true,cancelable:true});
                  var up = new KeyboardEvent('keyup', {key:ch,keyCode:code,which:code,bubbles:true,cancelable:true});
                  document.dispatchEvent(down); window.dispatchEvent(down);
                  document.dispatchEvent(up); window.dispatchEvent(up);
                  input.value = '';
                });
                document.body.appendChild(input);
              }
              input.focus();
            })();
        """.trimIndent()
        binding.gameWebView.requestFocus()
        binding.gameWebView.evaluateJavascript(script, null)
        val manager = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
        manager.showSoftInput(binding.gameWebView, InputMethodManager.SHOW_IMPLICIT)
    }

    fun onWebViewRenderProcessGone(view: WebView, didCrash: Boolean) {
        runOnUiThread {
            val wasGame = view === binding.gameWebView
            if (wasGame) {
                lastGameUrl = ""
                gameViewActive = false
                toolPageGameMode = false
                requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
                gamePreloaded = false
                clearTouchControls()
                binding.gameWebView.loadUrl("about:blank")
                binding.gameWebView.visibility = View.INVISIBLE
                binding.webView.visibility = View.VISIBLE
                updateToolButton()
                notifyWeb(if (didCrash) "Game renderer crashed. Please launch the game again." else "Game renderer was killed by the system. Please launch the game again.")
            } else {
                binding.webView.loadUrl("file:///android_asset/mobile_ui/index.html")
                notifyWeb("Tool page renderer recovered.")
            }
        }
    }

    private fun updateToolButton() {
        runOnUiThread {
            if (lastGameUrl.isBlank()) {
                binding.toolButton.visibility = View.GONE
                return@runOnUiThread
            }
            binding.toolButton.visibility = View.VISIBLE
            binding.toolButton.text = if (gameViewActive) "Tool" else "Back"
            binding.toolButton.alpha = if (gameViewActive) 0.72f else 0.86f
            binding.toolButton.bringToFront()
        }
    }

    fun pickGameFolder() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_PREFIX_URI_PERMISSION)
        }
        startActivityForResult(intent, pickGameFolderRequest)
    }

    fun pickGameExe() {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            putExtra(
                Intent.EXTRA_MIME_TYPES,
                arrayOf(
                    "application/x-msdownload",
                    "application/x-msdos-program",
                    "application/octet-stream"
                )
            )
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }
        startActivityForResult(intent, pickGameExeRequest)
    }

    fun selectGameFolder(uriText: String): String {
        return selectGamePath(uriText)
    }

    fun selectGamePath(uriText: String): String {
        return try {
            val raw = uriText.trim()
            val pathValue = when {
                raw.startsWith("exe:", ignoreCase = true) -> raw.removePrefix("exe:").removePrefix("EXE:")
                else -> raw
            }
            val uri = Uri.parse(pathValue)
            if (isLikelyExeUri(pathValue) || raw.startsWith("exe:", ignoreCase = true)) {
                lastExeUri = uri
                lastTreeUri = null
            } else {
                lastTreeUri = uri
                lastExeUri = null
            }
            cachedEntryPath = ""
            gameTreeRoot = null
            gameVirtualBase = ""
            gameAssetCache.clear()
            gameDirectoryCache.clear()
            apiCache.clear()
            gamePathIndex.clear()
            gameFileIndex = emptyMap()
            getPreferences(Context.MODE_PRIVATE)
                .edit()
                .putString("last_game_tree_uri", lastTreeUri?.toString().orEmpty())
                .putString("last_game_exe_uri", lastExeUri?.toString().orEmpty())
                .remove("last_rpg_entry_path")
                .apply()
            JSONObject().put("ok", true).toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }

    /**
     * Check whether imported library entries still exist on disk / SAF.
     * Never throws hard missing on permission/IO errors — prefer "unknown/exists"
     * so the library is not wiped by a flaky probe.
     */
    fun checkGamePaths(requestJson: String): String {
        return try {
            val root = JSONObject(requestJson.ifBlank { "{}" })
            val items = root.optJSONArray("items") ?: org.json.JSONArray()
            val results = org.json.JSONArray()
            var missing = 0
            for (i in 0 until items.length()) {
                val item = items.optJSONObject(i) ?: continue
                val key = item.optString("key").ifBlank {
                    item.optString("uri").ifBlank {
                        item.optString("exe_uri").ifBlank { item.optString("path") }
                    }
                }
                val exeUri = item.optString("exe_uri").ifBlank { item.optString("exe") }
                val treeUri = item.optString("uri").ifBlank {
                    item.optString("path").ifBlank { item.optString("game_path") }
                }
                val check = when {
                    exeUri.isNotBlank() && (isLikelyExeUri(exeUri) || exeUri.startsWith("content:", true) || exeUri.startsWith("file:", true)) ->
                        probeGameUri(exeUri, preferFile = true)
                    treeUri.isNotBlank() ->
                        probeGameUri(treeUri, preferFile = isLikelyExeUri(treeUri))
                    else -> Triple(true, "unknown", "路径为空(保留)")
                }
                // Only count definitive misses (probe returned exists=false with kind not unknown/error)
                if (!check.first && check.second != "unknown" && check.second != "error") missing += 1
                results.put(
                    JSONObject()
                        .put("key", key)
                        .put("exists", check.first)
                        .put("kind", check.second)
                        .put("label", check.third)
                )
            }
            JSONObject()
                .put("ok", true)
                .put("results", results)
                .put("missingCount", missing)
                .toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }

    private fun probeGameUri(raw: String, preferFile: Boolean): Triple<Boolean, String, String> {
        val value = raw.trim().removePrefix("exe:").removePrefix("EXE:")
        if (value.isBlank()) return Triple(true, "unknown", "路径为空")
        return try {
            when {
                value.startsWith("content:", ignoreCase = true) || value.startsWith("file:", ignoreCase = true) -> {
                    val uri = Uri.parse(value)
                    // Try both tree and single; SAF tree URIs often fail on fromSingleUri.
                    val tree = runCatching { DocumentFile.fromTreeUri(this, uri) }.getOrNull()
                    if (tree != null) {
                        val ok = runCatching { tree.exists() }.getOrDefault(true)
                        if (ok) return Triple(true, "folder", tree.name.orEmpty())
                    }
                    val single = runCatching { DocumentFile.fromSingleUri(this, uri) }.getOrNull()
                    if (single != null) {
                        val ok = runCatching { single.exists() }.getOrDefault(true)
                        if (ok) return Triple(true, "file", single.name.orEmpty())
                        // Definitive miss only when we could open the document handle.
                        return Triple(false, "file", "文件不存在")
                    }
                    // Permission lost or provider unavailable — keep the library entry.
                    Triple(true, "unknown", "暂时无法访问")
                }
                value.startsWith("/") || value.matches(Regex("^[A-Za-z]:\\\\.*")) -> {
                    val file = java.io.File(value)
                    val ok = file.exists()
                    if (ok) Triple(true, if (file.isDirectory) "folder" else "file", file.name)
                    else Triple(false, "file", "路径不存在")
                }
                else -> {
                    val uri = runCatching { Uri.parse(value) }.getOrNull()
                        ?: return Triple(true, "unknown", "无法解析路径")
                    val tree = runCatching { DocumentFile.fromTreeUri(this, uri) }.getOrNull()
                    if (tree != null && runCatching { tree.exists() }.getOrDefault(false)) {
                        return Triple(true, "folder", tree.name.orEmpty())
                    }
                    val single = runCatching { DocumentFile.fromSingleUri(this, uri) }.getOrNull()
                    if (single != null && runCatching { single.exists() }.getOrDefault(false)) {
                        return Triple(true, "file", single.name.orEmpty())
                    }
                    Triple(true, "unknown", "资源状态未知")
                }
            }
        } catch (error: Throwable) {
            Triple(true, "error", error.message ?: "检测失败")
        }
    }

    // ── Native game library (SharedPreferences) ──────────────────────────

    private val gameLibraryPrefs get() = getPreferences(Context.MODE_PRIVATE)
    private val GAME_LIBRARY_KEY = "game_library_json"

    fun androidGameLibrary(): String {
        return try {
            val raw = gameLibraryPrefs.getString(GAME_LIBRARY_KEY, "[]") ?: "[]"
            val arr = org.json.JSONArray(raw)
            JSONObject().put("ok", true).put("games", arr).put("count", arr.length()).toString()
        } catch (error: Throwable) {
            JSONObject().put("ok", false).put("error", error.message ?: error.javaClass.simpleName)
                .put("games", org.json.JSONArray()).toString()
        }
    }

    fun androidSaveGameLibrary(json: String): String {
        return try {
            val arr = when {
                json.isBlank() -> org.json.JSONArray()
                json.trimStart().startsWith("[") -> org.json.JSONArray(json)
                else -> {
                    val obj = JSONObject(json)
                    obj.optJSONArray("games") ?: org.json.JSONArray()
                }
            }
            // Cap at 60 entries
            val trimmed = org.json.JSONArray()
            for (i in 0 until minOf(arr.length(), 60)) trimmed.put(arr.get(i))
            gameLibraryPrefs.edit().putString(GAME_LIBRARY_KEY, trimmed.toString()).apply()
            JSONObject().put("ok", true).put("count", trimmed.length()).toString()
        } catch (error: Throwable) {
            JSONObject().put("ok", false).put("error", error.message ?: error.javaClass.simpleName).toString()
        }
    }

    fun androidRemoveGame(key: String): String {
        return try {
            val raw = gameLibraryPrefs.getString(GAME_LIBRARY_KEY, "[]") ?: "[]"
            val arr = org.json.JSONArray(raw)
            val next = org.json.JSONArray()
            val target = key.trim()
            for (i in 0 until arr.length()) {
                val item = arr.optJSONObject(i) ?: continue
                val k = libraryKeyOf(item)
                if (k != target) next.put(item)
            }
            gameLibraryPrefs.edit().putString(GAME_LIBRARY_KEY, next.toString()).apply()
            JSONObject().put("ok", true).put("count", next.length()).toString()
        } catch (error: Throwable) {
            JSONObject().put("ok", false).put("error", error.message ?: error.javaClass.simpleName).toString()
        }
    }

    /** Re-extract exe/png icon for an existing library entry and persist it. */
    fun androidRefreshGameIcon(key: String): String {
        return try {
            val target = key.trim()
            if (target.isBlank()) {
                return JSONObject().put("ok", false).put("error", "empty key").toString()
            }
            val raw = gameLibraryPrefs.getString(GAME_LIBRARY_KEY, "[]") ?: "[]"
            val arr = org.json.JSONArray(raw)
            var updated: JSONObject? = null
            for (i in 0 until arr.length()) {
                val item = arr.optJSONObject(i) ?: continue
                if (libraryKeyOf(item) != target) continue
                if (item.optString("iconDataUrl").isNotBlank()) {
                    return JSONObject().put("ok", true).put("iconDataUrl", item.optString("iconDataUrl"))
                        .put("cached", true).toString()
                }
                val exeUriText = item.optString("exe_uri").ifBlank { item.optString("exe") }
                var icon = ""
                if (exeUriText.startsWith("content:", true) || exeUriText.startsWith("file:", true)) {
                    icon = ExeIconExtractor.extractDataUrl(this, Uri.parse(exeUriText))
                }
                // Folder tree: try find exe under tree uri
                if (icon.isBlank()) {
                    val treeText = item.optString("uri").ifBlank { item.optString("path") }
                    if (treeText.startsWith("content:", true) || treeText.startsWith("file:", true)) {
                        val tree = runCatching { DocumentFile.fromTreeUri(this, Uri.parse(treeText)) }.getOrNull()
                        val exe = tree?.let { findFirstExe(it) }
                        if (exe != null) {
                            icon = ExeIconExtractor.extractDataUrl(this, exe.uri)
                            if (icon.isNotBlank()) item.put("exe_uri", exe.uri.toString())
                        }
                    }
                }
                if (icon.isBlank()) {
                    return JSONObject().put("ok", false).put("error", "no icon").toString()
                }
                item.put("iconDataUrl", icon)
                arr.put(i, item)
                updated = item
                break
            }
            if (updated == null) {
                return JSONObject().put("ok", false).put("error", "not found").toString()
            }
            gameLibraryPrefs.edit().putString(GAME_LIBRARY_KEY, arr.toString()).apply()
            JSONObject().put("ok", true).put("iconDataUrl", updated.optString("iconDataUrl")).toString()
        } catch (error: Throwable) {
            JSONObject().put("ok", false).put("error", error.message ?: error.javaClass.simpleName).toString()
        }
    }

    fun upsertGameLibraryEntry(payload: JSONObject) {
        try {
            val key = libraryKeyOf(payload)
            if (key.isBlank()) return
            val raw = gameLibraryPrefs.getString(GAME_LIBRARY_KEY, "[]") ?: "[]"
            val arr = org.json.JSONArray(raw)
            val next = org.json.JSONArray()
            val entry = JSONObject(payload.toString())
            if (!entry.has("id")) entry.put("id", key)
            if (!entry.has("title") || entry.optString("title").isBlank()) {
                entry.put("title", payload.optString("name").ifBlank { "Game" })
            }
            // Preserve previous icon if new scan didn't produce one
            for (i in 0 until arr.length()) {
                val old = arr.optJSONObject(i) ?: continue
                if (libraryKeyOf(old) != key) continue
                if (entry.optString("iconDataUrl").isBlank() && old.optString("iconDataUrl").isNotBlank()) {
                    entry.put("iconDataUrl", old.optString("iconDataUrl"))
                }
                break
            }
            next.put(entry)
            for (i in 0 until arr.length()) {
                val item = arr.optJSONObject(i) ?: continue
                if (libraryKeyOf(item) == key) continue
                next.put(item)
                if (next.length() >= 60) break
            }
            gameLibraryPrefs.edit().putString(GAME_LIBRARY_KEY, next.toString()).apply()
        } catch (error: Throwable) {
            Log.w("RPGTL", "upsertGameLibraryEntry failed", error)
        }
    }

    private fun libraryKeyOf(item: JSONObject): String {
        return item.optString("uri").ifBlank {
            item.optString("exe_uri").ifBlank {
                item.optString("exe").ifBlank {
                    item.optString("path").ifBlank {
                        item.optString("game_path").ifBlank {
                            item.optString("root").ifBlank { item.optString("id") }
                        }
                    }
                }
            }
        }
    }

    fun launchSelectedGame() {
        val uri = lastTreeUri
        if (uri == null) {
            notifyWeb("Please select a game folder first.")
            return
        }
        Thread {
            val sessionId = nextRunSession()
            try {
                notifyWeb("Checking RPG Maker MV/MZ entry...")
                val source = DocumentFile.fromTreeUri(this, uri)
                    ?: throw IllegalStateException("Cannot read selected folder.")
                val sourceEntry = cachedEntryPath.takeIf { it.isNotBlank() && isValidRpgMakerEntryPath(source, it) }
                    ?: findRpgMakerEntryPath(source)
                    ?: throw IllegalStateException("MV/MZ entry not found. Select a folder containing a valid RPG Maker www/index.html or index.html, not a tool loader page.")
                cachedEntryPath = sourceEntry
                getPreferences(Context.MODE_PRIVATE)
                    .edit()
                    .putString("last_rpg_entry_path", sourceEntry)
                    .apply()
                gameTreeRoot = source
                gameVirtualBase = sourceEntry.substringBeforeLast("/", "")
                gameAssetCache.clear()
                gameDirectoryCache.clear()
                apiCache.clear()
                gamePathIndex.clear()
                gameFileIndex = emptyMap()
                restoreGamePathIndex(uri)
                buildGameFileIndex(source, uri)
                val virtualEntry = "https://rpgrtl.local/game/$sourceEntry"
                lastGameUrl = virtualEntry
                toolPageGameMode = false
                gameViewActive = true
                requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                gamePreloaded = false
                notifyWeb("On-demand mode enabled. Entry: $sourceEntry")
                runOnUiThread {
                    if (sessionId != runSessionId) return@runOnUiThread
                    updateToolButton()
                    applyLaunchSettings()
                    showGameLoadingOverlay("Opening RPG Maker in built-in WebView...")
                    binding.webView.visibility = View.GONE
                    binding.gameWebView.visibility = View.VISIBLE
                    binding.gameWebView.loadUrl(virtualEntry)
                    binding.gameWebView.postDelayed({ if (gameViewActive) applyTouchControls() }, 700)
                }
            } catch (error: Throwable) {
                if (sessionId == runSessionId) {
                    hideGameLoadingOverlay(0)
                    notifyWeb("Launch failed: ${error.message}")
                }
            }
        }.start()
    }

    fun scanSelectedGame() {
        scanSelectedGamePath("")
    }

    fun scanSelectedGamePath(uriText: String) {
        if (uriText.isNotBlank()) {
            selectGamePath(uriText)
        }
        val exeUri = lastExeUri
        if (exeUri != null) {
            dispatchProjectScanned(scanSingleExe(exeUri))
            return
        }
        val uri = lastTreeUri
        if (uri == null) {
            notifyWeb("Please select a game folder first.")
            return
        }
        Thread {
            try {
                notifyWeb("Scanning folder...")
                val source = DocumentFile.fromTreeUri(this, uri)
                    ?: throw IllegalStateException("Cannot read selected folder.")
                val result = scanGameTree(source, uri)
                if (result.optString("rpgEntry").isNotBlank() && result.optString("engine") == "RPG Maker MV/MZ") {
                    prepareScannedRpgMakerOnMain(source, result.optString("rpgEntry"), uri)
                }
                dispatchProjectScanned(result)
            } catch (error: Throwable) {
                notifyWeb("Scan failed: ${error.message}")
            }
        }.start()
    }

    private fun prepareScannedRpgMakerOnMain(root: DocumentFile, rpgEntry: String, uri: Uri) {
        if (rpgEntry.isBlank()) return
        runOnUiThread {
            gameTreeRoot = root
            gameVirtualBase = rpgEntry.substringBeforeLast("/", "")
            cachedEntryPath = rpgEntry
            lastGameUrl = "https://rpgrtl.local/game/$rpgEntry"
            gamePreloaded = false
            getPreferences(Context.MODE_PRIVATE)
                .edit()
                .putString("last_rpg_entry_path", rpgEntry)
                .apply()
            restoreGamePathIndex(uri)
            buildGameFileIndex(root, uri)
            updateToolButton()
        }
    }

    fun launchRenpyGame() {
        val uri = lastTreeUri
        if (uri == null) {
            notifyWeb("Please select a game folder first.")
            return
        }
        Thread {
            val sessionId = nextRunSession()
            try {
                notifyWeb("Checking RenPy Android/Web entry...")
                val source = DocumentFile.fromTreeUri(this, uri)
                    ?: throw IllegalStateException("Cannot read selected folder.")
                if (findRenpyWebEntry(source) != null) {
                    notifyWeb("RenPy Web entry found. Preparing runtime files...")
                    val localRoot = File(cacheDir, "rpgrtl_renpy_runtime").apply {
                        deleteRecursively()
                        mkdirs()
                    }
                    copyDocumentTree(source, localRoot)
                    val localEntry = findRenpyWebEntry(localRoot)
                        ?: throw IllegalStateException("RenPy Web index.html not found after copy.")
                    runOnUiThread {
                        if (sessionId != runSessionId) return@runOnUiThread
                        lastGameUrl = localEntry.toURI().toString()
                        toolPageGameMode = false
                        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
                        gameViewActive = true
                        updateToolButton()
                        showGameLoadingOverlay("Preparing RenPy Web runtime files...")
                        binding.webView.visibility = View.GONE
                        binding.gameWebView.visibility = View.VISIBLE
                        binding.gameWebView.loadUrl(lastGameUrl)
                        binding.gameWebView.postDelayed({ if (gameViewActive) applyTouchControls() }, 700)
                    }
                    notifyWeb("RenPy Web entry opened in WebView.")
                    return@Thread
                }
                val exe = findFirstExe(source)
                if (exe != null) {
                    runOnUiThread {
                        if (sessionId != runSessionId) return@runOnUiThread
                        val title = displayNameForUri(exe.uri).ifBlank { "Ren'Py Game" }
                        notifyWeb("Starting Ren'Py with built-in Winlator...")
                        WineEngineBridge(this).launch(gameUri = exe.uri, title = title, gameTreeUri = uri)
                    }
                    return@Thread
                }
                notifyWeb("RenPy resources found, but no Android/Web entry was found. Use a compatible runner for Windows exe games.")
            } catch (error: Throwable) {
                if (sessionId == runSessionId) {
                    hideGameLoadingOverlay(0)
                    notifyWeb("RenPy launch failed: ${error.message}")
                }
            }
        }.start()
    }

    fun launchExeWithExternalRunner() {
        val uri = lastTreeUri
        if (uri == null) {
            notifyWeb("Please select a game folder first.")
            return
        }
        Thread {
            val sessionId = nextRunSession()
            try {
                notifyWeb("Looking for exe file...")
                val source = DocumentFile.fromTreeUri(this, uri)
                    ?: throw IllegalStateException("Cannot read selected folder.")
                val exe = findFirstExe(source)
                    ?: throw IllegalStateException("No exe file found in selected folder.")
                runOnUiThread {
                    if (sessionId != runSessionId) return@runOnUiThread
                    val title = displayNameForUri(exe.uri).ifBlank { "Windows Game" }
                    notifyWeb("Starting exe with built-in Winlator...")
                    WineEngineBridge(this).launch(gameUri = exe.uri, title = title, gameTreeUri = uri)
                }
            } catch (error: Throwable) {
                if (sessionId == runSessionId) notifyWeb("Open exe failed: ${error.message}")
            }
        }.start()
    }

    fun androidTranslationEntries(limit: Int): String {
        return cachedAndroidRpgResult("translations:$limit") { service ->
            service.translationEntries(limit)
        }
    }

    fun androidDataRecords(requestJson: String): String {
        val request = try {
            JSONObject(requestJson)
        } catch (_: Throwable) {
            JSONObject().put("category", requestJson)
        }
        val category = request.optString("category", "")
        val limit = request.optInt("limit", Int.MAX_VALUE).let { if (it <= 0) Int.MAX_VALUE else it }
        return cachedAndroidRpgResult("records:$category:$limit") { service ->
            service.dataRecords(category, limit)
        }
    }

    fun androidDataRecords(category: String, limit: Int): String {
        return androidDataRecords(JSONObject().put("category", category).put("limit", limit).toString())
    }

    fun androidUpdateRecord(recordJson: String, newValue: String): String {
        apiCache.clear()
        return androidRpgServiceResult { service ->
            service.updateRecord(recordJson, newValue)
        }
    }

    fun androidSaveTranslationEntries(requestJson: String): String {
        apiCache.clear()
        return androidRpgServiceResult { service ->
            service.saveTranslationEntries(requestJson)
        }
    }

    fun androidMaps(): String {
        return cachedAndroidRpgResult("maps") { service ->
            service.maps()
        }
    }

    fun androidMapDetail(mapId: Int): String {
        return cachedAndroidRpgResult("mapDetail:$mapId") { service ->
            service.mapDetail(mapId)
        }
    }

    fun androidSaveSlots(): String {
        if (isWineContext()) {
            return WineSaveService(this).saveSlots(externalContainerId, externalGamePath).toString()
        }
        return cachedAndroidRpgResult("saveSlots") { service ->
            service.saveSlots()
        }
    }

    fun androidCreateSaveBackup(): String {
        if (isWineContext()) {
            return WineSaveService(this).createBackup(externalContainerId, externalGamePath).toString()
        }
        return androidRpgServiceResult { service ->
            service.createSaveBackup()
        }
    }

    fun androidBackups(): String {
        if (isWineContext()) {
            return WineSaveService(this).backups(externalContainerId, externalGamePath).toString()
        }
        return cachedAndroidRpgResult("backups") { service ->
            service.backups()
        }
    }

    fun androidGetSavePath(): String {
        if (isWineContext()) {
            return WineSaveService(this).savePath(externalContainerId, externalGamePath).toString()
        }
        return androidRpgServiceResult { service -> service.savePath() }
    }

    fun androidAiSettings(): String {
        val saved = getPreferences(Context.MODE_PRIVATE)
            .getString("android_ai_settings_json", "") ?: ""
        if (saved.isNotBlank()) return saved
        return JSONObject()
            .put("provider", "openai")
            .put("baseUrl", "https://api.openai.com/v1")
            .put("apiKey", "")
            .put("model", "gpt-4o-mini")
            .put("batchSize", 20)
            .put("concurrency", 1)
            .put("requestIntervalMs", 1200)
            .put("requestTimeoutSec", 240)
            .put("targetLang", "简体中文")
            .toString()
    }

    fun saveAiSettings(json: String): String {
        return try {
            JSONObject(json)
            getPreferences(Context.MODE_PRIVATE)
                .edit()
                .putString("android_ai_settings_json", json)
                .apply()
            JSONObject()
                .put("ok", true)
                .put("message", "AI settings saved.")
                .toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }

    fun androidAiTranslate(requestJson: String): String {
        return try {
            val request = JSONObject(requestJson)
            val currentSettings = request.optJSONObject("settings")
            if (currentSettings == null || currentSettings.length() == 0) {
                val saved = getPreferences(Context.MODE_PRIVATE)
                    .getString("android_ai_settings_json", "") ?: ""
                if (saved.isNotBlank()) request.put("settings", JSONObject(saved))
            } else if (currentSettings.has("ai")) {
                request.put("settings", currentSettings.optJSONObject("ai") ?: currentSettings)
            }
            AndroidAiTranslationService().translate(request).toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }

    fun runtimeStatus(): String {
        wineRuntimeBridge()?.let { return it.status().toString() }
        val script = """
            (function(){
              try {
                if (!window.RPGCHEAT) return JSON.stringify({ok:false,error:'cheat script is not injected'});
                return window.RPGCHEAT.status();
              } catch(e) {
                return JSON.stringify({ok:false,error:String(e)});
              }
            })();
        """.trimIndent()
        return evalGameJson(script)
    }

    fun runtimeCheat(action: String, value: String): String {
        wineRuntimeBridge()?.let { bridge ->
            val mapped = when (action) {
                "gold" -> "setGold"
                "hp" -> "setHp"
                "mp" -> "setMp"
                "tp" -> "setTp"
                "through" -> "noclip"
                else -> action
            }
            return bridge.command(mapped, value).toString()
        }
        val safeAction = escapeJs(action)
        val safeValue = escapeJs(value)
        val script = """
            (function(){
              try {
                if (!window.RPGCHEAT) return JSON.stringify({ok:false,error:'cheat script is not injected'});
                return window.RPGCHEAT.run('$safeAction', '$safeValue');
              } catch(e) {
                return JSON.stringify({ok:false,error:String(e)});
              }
            })();
        """.trimIndent()
        return evalGameJson(script)
    }

    fun androidAiModels(settingsJson: String): String {
        return try {
            AndroidAiTranslationService().listModels(JSONObject(settingsJson)).toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }

    fun androidRuntimeEval(script: String): String {
        wineRuntimeBridge()?.let { bridge ->
            return bridge.evaluate(script).toString()
        }
        val wrapped = """
            (function(){
              try {
                return JSON.stringify({ok:true,value:(function(){ return ($script); })()});
              } catch(e) {
                return JSON.stringify({ok:false,error:String(e)});
              }
            })();
        """.trimIndent()
        return evalGameJson(wrapped)
    }

    private fun wineRuntimeBridge(): com.rpgrtl.shell.wine.RuntimeBridge? {
        if (externalSourceApp != "rpgtl_wine" || externalContainerId < 0) return null
        return WineDisplayActivity.runtimeBridgeFor(externalContainerId)
    }

    fun injectCheatScript() {
        val source = try {
            if (cheatScriptSource.isBlank()) {
                cheatScriptSource = assets.open("scripts/rpgmv-cheat.js").bufferedReader().use { it.readText() }
            }
            cheatScriptSource
        } catch (error: Throwable) {
            Log.e("Cheat", "Failed to read cheat script", error)
            return
        }
        runOnUiThread {
            binding.gameWebView.evaluateJavascript(source, null)
        }
    }

    fun injectGameErrorCollector(view: WebView?) {
        val script = try {
            assets.open("scripts/game-error-collector.js").bufferedReader().use { it.readText() }
        } catch (error: Throwable) {
            Log.e("GAME_JS", "Failed to load error collector", error)
            return
        }
        view?.evaluateJavascript(script, null)
    }

    private fun evalGameJson(script: String): String {
        val latch = java.util.concurrent.CountDownLatch(1)
        val result = arrayOf("{\"ok\":false,\"error\":\"timeout\"}")
        runOnUiThread {
            binding.gameWebView.evaluateJavascript(script) { raw ->
                val cleaned = raw
                    ?.removeSurrounding("\"")
                    ?.replace("\\\"", "\"")
                    ?.replace("\\\\", "\\")
                    ?: "{\"ok\":false,\"error\":\"empty\"}"
                result[0] = cleaned
                latch.countDown()
            }
        }
        latch.await(1200, java.util.concurrent.TimeUnit.MILLISECONDS)
        return result[0]
    }

    private fun androidRpgServiceResult(block: (AndroidRpgMakerService) -> JSONObject): String {
        return try {
            val uri = lastTreeUri ?: throw IllegalStateException("Please select a game folder first.")
            val source = DocumentFile.fromTreeUri(this, uri)
                ?: throw IllegalStateException("Cannot read selected folder.")
            block(AndroidRpgMakerService(this, source, externalServiceContext())).toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }

    private fun isWineContext(): Boolean {
        return externalSourceApp == "rpgtl_wine" && externalContainerId >= 0
    }

    private fun externalServiceContext(): JSONObject {
        return JSONObject()
            .put("source_app", externalSourceApp)
            .put("container_id", externalContainerId)
            .put("container_name", externalContainerName)
            .put("game_path", externalGamePath)
    }

    private fun cachedAndroidRpgResult(cacheKey: String, block: (AndroidRpgMakerService) -> JSONObject): String {
        apiCache[cacheKey]?.let { return it }
        return try {
            val future = apiPool.submit(Callable {
                androidRpgServiceResult(block)
            })
            val result = future.get(8, TimeUnit.SECONDS)
            apiCache[cacheKey] = result
            result
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }

    fun openOverlaySettings() {
        val intent = Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:$packageName")
        )
        startActivity(intent)
    }

    fun saveTouchControls(json: String) {
        getPreferences(Context.MODE_PRIVATE)
            .edit()
            .putString("touch_controls_json", json)
            .apply()
        if (binding.toolButton.visibility == View.VISIBLE) {
            applyTouchControls()
        }
        notifyWeb("Touch control layout saved.")
    }

    fun saveLaunchSettings(json: String): String {
        return try {
            JSONObject(json)
            getPreferences(Context.MODE_PRIVATE)
                .edit()
                .putString("launch_settings_json", json)
                .apply()
            runOnUiThread {
                applyLaunchSettings()
                if (gameViewActive && lastGameUrl.isNotBlank()) {
                    binding.gameWebView.reload()
                }
                notifyWeb("Launch settings saved.")
            }
            JSONObject().put("ok", true).put("message", "Launch settings saved.").toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
                .toString()
        }
    }

    private fun applyLaunchSettings() {
        val raw = getPreferences(Context.MODE_PRIVATE).getString("launch_settings_json", "") ?: ""
        val settings = try {
            if (raw.isBlank()) JSONObject() else JSONObject(raw)
        } catch (_: Throwable) {
            JSONObject()
        }
        val webgl = settings.optBoolean("webgl", true)
        val domStorage = settings.optBoolean("domStorage", true)
        val fileAccess = settings.optBoolean("fileAccess", true)
        val mediaAutoplay = settings.optBoolean("mediaAutoplay", true)
        val disableZoom = settings.optBoolean("disableZoom", true)
        listOf(binding.webView, binding.gameWebView).forEach { target ->
            with(target.settings) {
                domStorageEnabled = domStorage
                databaseEnabled = domStorage
                allowFileAccess = fileAccess
                allowContentAccess = fileAccess
                allowFileAccessFromFileURLs = fileAccess
                allowUniversalAccessFromFileURLs = fileAccess
                mediaPlaybackRequiresUserGesture = !mediaAutoplay
                setSupportZoom(!disableZoom)
                builtInZoomControls = !disableZoom
                displayZoomControls = false
                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                textZoom = 100
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    offscreenPreRaster = true
                }
            }
            target.setLayerType(if (webgl) View.LAYER_TYPE_HARDWARE else View.LAYER_TYPE_SOFTWARE, null)
            target.overScrollMode = View.OVER_SCROLL_NEVER
        }
        binding.webView.settings.textZoom = 82
        binding.gameWebView.settings.textZoom = 100
        applyRenderMode(settings.optString("renderMode", "fast"))
    }

    private fun applyRenderMode(mode: String) {
        with(binding.gameWebView.settings) {
            when (mode) {
                "compat" -> {
                    userAgentString = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    // Desktop UA helps compatibility, but overview mode makes many games render zoomed-in on phones.
                    useWideViewPort = false
                    loadWithOverviewMode = false
                    cacheMode = WebSettings.LOAD_DEFAULT
                    layoutAlgorithm = WebSettings.LayoutAlgorithm.NORMAL
                }
                else -> {
                    userAgentString = null
                    useWideViewPort = false
                    loadWithOverviewMode = false
                    cacheMode = WebSettings.LOAD_CACHE_ELSE_NETWORK
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                        offscreenPreRaster = true
                    }
                    layoutAlgorithm = WebSettings.LayoutAlgorithm.NORMAL
                }
            }
        }
    }

    @Deprecated("Deprecated in Android API but fine for this minimal shell prototype.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        val flags = data.flags and (
            Intent.FLAG_GRANT_READ_URI_PERMISSION or
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
        runCatching { contentResolver.takePersistableUriPermission(uri, flags) }
        when (requestCode) {
            pickGameFolderRequest -> {
                lastTreeUri = uri
                lastExeUri = null
                getPreferences(Context.MODE_PRIVATE)
                    .edit()
                    .putString("last_game_tree_uri", uri.toString())
                    .putString("last_game_exe_uri", "")
                    .apply()
                dispatchFolderPicked(uri)
            }
            pickGameExeRequest -> {
                lastExeUri = uri
                lastTreeUri = null
                getPreferences(Context.MODE_PRIVATE)
                    .edit()
                    .putString("last_game_tree_uri", "")
                    .putString("last_game_exe_uri", uri.toString())
                    .apply()
                dispatchExePicked(uri)
            }
        }
    }

    private fun restoreLastTreeUri() {
        val raw = getPreferences(Context.MODE_PRIVATE).getString("last_game_tree_uri", "") ?: ""
        if (raw.isNotBlank()) {
            lastTreeUri = Uri.parse(raw)
        }
        val exeRaw = getPreferences(Context.MODE_PRIVATE).getString("last_game_exe_uri", "") ?: ""
        if (exeRaw.isNotBlank()) {
            lastExeUri = Uri.parse(exeRaw)
        }
        cachedEntryPath = getPreferences(Context.MODE_PRIVATE).getString("last_rpg_entry_path", "") ?: ""
    }

    private fun dispatchFolderPicked(uri: Uri) {
        val escaped = escapeJs(uri.toString())
        runOnUiThread {
            binding.webView.evaluateJavascript(
                "window.onAndroidGameFolderPicked && window.onAndroidGameFolderPicked('$escaped')",
                null
            )
            scanSelectedGame()
        }
    }

    private fun dispatchExePicked(uri: Uri) {
        val escaped = escapeJs(uri.toString())
        runOnUiThread {
            binding.webView.evaluateJavascript(
                "window.onAndroidGameExePicked && window.onAndroidGameExePicked('$escaped')",
                null
            )
        }
        dispatchProjectScanned(scanSingleExe(uri))
    }

    fun dispatchRestoredFolderIfAny() {
        val uri = lastTreeUri ?: return
        dispatchFolderPicked(uri)
    }

    private fun dispatchProjectScanned(payload: JSONObject) {
        // Persist into native library so entries survive WebView cache wipes.
        upsertGameLibraryEntry(payload)
        val escaped = escapeJs(payload.toString())
        runOnUiThread {
            binding.webView.evaluateJavascript(
                "window.onAndroidProjectScanned && window.onAndroidProjectScanned('$escaped')",
                null
            )
        }
    }

    fun notifyWeb(message: String) {
        ShellLog.info(this, message)
        val escaped = escapeJs(message)
        runOnUiThread {
            binding.webView.evaluateJavascript(
                "window.onAndroidShellMessage && window.onAndroidShellMessage('$escaped')",
                null
            )
        }
    }

    fun androidRenpyLiveStatus(): String {
        return com.rpgrtl.shell.wine.RenPyLiveTranslationService.currentStatus()
    }

    private fun appVersionLabel(): String {
        return try {
            val info = packageManager.getPackageInfo(packageName, 0)
            val code = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                info.longVersionCode
            } else {
                @Suppress("DEPRECATION")
                info.versionCode.toLong()
            }
            "v=${info.versionName} code=$code"
        } catch (_: Throwable) {
            "v=unknown"
        }
    }

    fun androidRuntimeLog(): String {
        return try {
            JSONObject()
                .put("ok", true)
                .put("log", ShellLog.read(this))
                .toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: "read log failed")
                .toString()
        }
    }

    fun androidLaunchSettings(): String {
        return getPreferences(Context.MODE_PRIVATE)
            .getString("launch_settings_json", "")
            ?.takeIf { it.isNotBlank() }
            ?: JSONObject()
                .put("game", JSONObject()
                    .put("renpy", JSONObject()
                        .put("hardwareVideoDecode", true)
                        .put("liveTranslation", true)
                        .put("lowMemory", false))
                    .put("html", JSONObject().put("webgl", true))
                    .put("rpg", JSONObject()
                        .put("directoryCache", true)
                        .put("prebuildPathCache", true)
                        .put("translationInject", false)
                        .put("resourceFallback", true)
                        .put("smoothScaling", true)
                        .put("resizeLargeTextures", true)
                        .put("fastForwardSpeed", 1)
                        .put("fontScale", 0.75)))
                .toString()
    }

    fun clearRuntimeLog(): String {
        return try {
            ShellLog.clear(this)
            JSONObject().put("ok", true).toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: "clear log failed")
                .toString()
        }
    }

    fun copyRuntimeLog(): String {
        return try {
            val logText = ShellLog.read(this).ifBlank { "No runtime log." }
            val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            clipboard.setPrimaryClip(ClipData.newPlainText("RPGRenPyLocalizer runtime log", logText))
            JSONObject().put("ok", true).put("chars", logText.length).toString()
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: "copy log failed")
                .toString()
        }
    }

    private fun pushToolModeContext() {
        val mode = if (toolPageGameMode) "game" else "workspace"
        val context = JSONObject()
            .put("mode", mode)
            .put("game_mode", if (toolPageGameMode) "in_game" else "workspace")
            .put("has_game", lastGameUrl.isNotBlank())
            .put("engine", when {
                lastGameUrl.contains("rpgrtl.local", ignoreCase = true) -> "RPG Maker MV/MZ"
                lastGameUrl.contains("renpy", ignoreCase = true) -> "Ren'Py"
                else -> ""
            })
            .put("game_title", externalGameTitle.ifBlank { externalContainerName.ifBlank { "Loaded game" } })
        val escaped = escapeJs(context.toString())
        binding.webView.evaluateJavascript(
            "window.onAndroidToolMode&&window.onAndroidToolMode(JSON.parse('$escaped'));window.onAndroidExternalLaunchContext&&window.onAndroidExternalLaunchContext(JSON.parse('$escaped'))",
            null
        )
    }

    private fun pushExternalLaunchContext() {
        val context = getPreferences(Context.MODE_PRIVATE).getString("external_launch_context", "") ?: ""
        if (context.isBlank()) return
        val escaped = escapeJs(context)
        binding.webView.evaluateJavascript(
            "window.onAndroidExternalLaunchContext && window.onAndroidExternalLaunchContext(JSON.parse('$escaped'));window.onAndroidOpenToolPage&&window.onAndroidOpenToolPage(JSON.parse('$escaped').target_page||'')",
            null
        )
    }

    private fun nextRunSession(): Int {
        runSessionId += 1
        return runSessionId
    }

    private fun applyTouchControls() {
        clearTouchControls()
        addNativeTouchControls()
    }

    private fun addNativeTouchControls() {
        val raw = getPreferences(Context.MODE_PRIVATE).getString("touch_controls_json", "") ?: minimalTouchControlsJson()
        val config = try { JSONObject(raw) } catch (_: Throwable) { JSONObject(minimalTouchControlsJson()) }
        if (!config.optBoolean("enabled", true)) return
        val buttons = config.optJSONArray("buttons") ?: return
        val rootWidth = binding.root.width.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
        val rootHeight = binding.root.height.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
        for (index in 0 until buttons.length()) {
            val item = buttons.optJSONObject(index) ?: continue
            if (!item.optBoolean("enabled", true)) continue
            val isJoystick = item.optString("kind") == "joystick" || item.optString("id") == "joystick"
            val sizeDp = item.optDouble("size", if (isJoystick) 112.0 else 52.0)
            val size = dp(sizeDp.coerceIn(34.0, 150.0).toFloat())
            val x = item.optDouble("x", 0.5).coerceIn(0.02, 0.98)
            val y = item.optDouble("y", 0.5).coerceIn(0.04, 0.96)
            val normalBgColor = if (isJoystick) 0x553C9DFF else 0xCC0D1726.toInt()
            val pressedBgColor = 0xEE4DD6C8.toInt()
            val normalTextColor = 0xEEFFFFFF.toInt()
            val pressedTextColor = 0xFF06111C.toInt()
            val normalStrokeColor = 0xAA4DD6C8.toInt()
            fun makeDrawable(pressed: Boolean) = android.graphics.drawable.GradientDrawable().apply {
                shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                cornerRadius = if (isJoystick) size / 2f else dp(10f).toFloat()
                setColor(if (pressed) pressedBgColor else normalBgColor)
                setStroke(dp(1.5f), if (pressed) 0xFFFFFFFF.toInt() else normalStrokeColor)
            }
            val view = TextView(this).apply {
                text = if (isJoystick) "◎" else item.optString("label", "A")
                textSize = if (isJoystick) 22f else 15f
                gravity = android.view.Gravity.CENTER
                setTextColor(normalTextColor)
                alpha = item.optDouble("opacity", 0.68).coerceIn(0.18, 1.0).toFloat()
                background = makeDrawable(false)
            }
            val left = (rootWidth * x - size / 2.0).toInt().coerceIn(0, (rootWidth - size).coerceAtLeast(0))
            val top = (rootHeight * y - size / 2.0).toInt().coerceIn(0, (rootHeight - size).coerceAtLeast(0))
            val params = FrameLayout.LayoutParams(size, size).apply {
                leftMargin = left
                topMargin = top
            }
            if (isJoystick) {
                var activeDirs = mutableSetOf<Int>()
                fun setDirections(newDirs: Set<Int>) {
                    val toRelease = activeDirs - newDirs
                    val toPress = newDirs - activeDirs
                    toRelease.forEach { dispatchKeyToGame(it, KeyEvent.ACTION_UP) }
                    toPress.forEach { dispatchKeyToGame(it, KeyEvent.ACTION_DOWN) }
                    activeDirs = newDirs.toMutableSet()
                }
                fun release() {
                    activeDirs.forEach { dispatchKeyToGame(it, KeyEvent.ACTION_UP) }
                    activeDirs.clear()
                }
                view.setOnTouchListener { _, event ->
                    when (event.actionMasked) {
                        android.view.MotionEvent.ACTION_DOWN -> {
                            view.background = makeDrawable(true)
                            view.setTextColor(pressedTextColor)
                            runCatching { view.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY) }
                            true
                        }
                        android.view.MotionEvent.ACTION_MOVE -> {
                            val dx = event.x - size / 2f
                            val dy = event.y - size / 2f
                            val dist = kotlin.math.hypot(dx.toDouble(), dy.toDouble())
                            val deadzone = dp(8f)
                            if (dist < deadzone) {
                                release()
                            } else {
                                val angle = (Math.toDegrees(Math.atan2(dy.toDouble(), dx.toDouble())) + 360) % 360
                                val dirs = when {
                                    angle >= 337.5 || angle < 22.5 -> setOf(KeyEvent.KEYCODE_DPAD_RIGHT)
                                    angle in 22.5..67.5 -> setOf(KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT)
                                    angle in 67.5..112.5 -> setOf(KeyEvent.KEYCODE_DPAD_DOWN)
                                    angle in 112.5..157.5 -> setOf(KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.KEYCODE_DPAD_LEFT)
                                    angle in 157.5..202.5 -> setOf(KeyEvent.KEYCODE_DPAD_LEFT)
                                    angle in 202.5..247.5 -> setOf(KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_LEFT)
                                    angle in 247.5..292.5 -> setOf(KeyEvent.KEYCODE_DPAD_UP)
                                    angle in 292.5..337.5 -> setOf(KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_RIGHT)
                                    else -> emptySet()
                                }
                                setDirections(dirs)
                            }
                            true
                        }
                        android.view.MotionEvent.ACTION_UP,
                        android.view.MotionEvent.ACTION_CANCEL -> {
                            view.background = makeDrawable(false)
                            view.setTextColor(normalTextColor)
                            release()
                            true
                        }
                        else -> true
                    }
                }
            } else {
                val keyCode = item.optInt("keyCode", KeyEvent.KEYCODE_ENTER)
                view.setOnTouchListener { _, event ->
                    when (event.actionMasked) {
                        android.view.MotionEvent.ACTION_DOWN -> {
                            view.background = makeDrawable(true)
                            view.setTextColor(pressedTextColor)
                            runCatching { view.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY) }
                            dispatchKeyToGame(keyCode, KeyEvent.ACTION_DOWN)
                            true
                        }
                        android.view.MotionEvent.ACTION_UP,
                        android.view.MotionEvent.ACTION_CANCEL -> {
                            view.background = makeDrawable(false)
                            view.setTextColor(normalTextColor)
                            dispatchKeyToGame(keyCode, KeyEvent.ACTION_UP)
                            true
                        }
                        else -> true
                    }
                }
            }
            binding.root.addView(view, params)
            view.bringToFront()
            touchButtonViews.add(view)
        }
        binding.toolButton.bringToFront()
    }

    private fun dp(value: Float): Int {
        return (value * resources.displayMetrics.density + 0.5f).toInt()
    }

    private fun reflowWebViewSoon() {
        applySystemUiForCurrentMode()
        val target = if (gameViewActive) binding.gameWebView else binding.webView
        target.postDelayed({
            val setZoom = ""
            target.evaluateJavascript(
                """
                (function(){
                  if(document.body && document.body.style){
                    document.body.style.display = '';
                    $setZoom
                  }
                  window.dispatchEvent(new Event('resize'));
                  document.dispatchEvent(new Event('resize'));
                })();
                """.trimIndent(),
                null
            )
        }, 100)
    }

    private fun defaultTouchControlsJson(): String {
        return """
            {
              "enabled": true,
              "buttons": [
                {"id":"joystick","kind":"joystick","label":"鎽囨潌","x":0.17,"y":0.72,"size":150,"opacity":0.62,"enabled":true},
                {"id":"ok","label":"A","keyCode":66,"x":0.84,"y":0.66,"size":68,"opacity":0.70,"enabled":true},
                {"id":"cancel","label":"B","keyCode":4,"x":0.72,"y":0.76,"size":62,"opacity":0.58,"enabled":true},
                {"id":"dash","label":"璺?,"keyCode":59,"x":0.87,"y":0.42,"size":54,"opacity":0.48,"enabled":true},
                {"id":"fast","label":"蹇?,"keyCode":113,"x":0.74,"y":0.42,"size":54,"opacity":0.48,"enabled":true}
              ]
            }
        """.trimIndent()
    }

    private fun minimalTouchControlsJson(): String {
        return """
            {
              "enabled": true,
              "buttons": [
                {"id":"joystick","kind":"joystick","label":"Joystick","x":0.17,"y":0.72,"size":150,"opacity":0.62,"enabled":true},
                {"id":"ok","label":"A","keyCode":66,"x":0.84,"y":0.66,"size":68,"opacity":0.70,"enabled":true},
                {"id":"cancel","label":"B","keyCode":4,"x":0.72,"y":0.76,"size":62,"opacity":0.58,"enabled":true}
              ]
            }
        """.trimIndent()
    }

    fun reapplyGameOverlay() {
        runOnUiThread {
            if (gameViewActive) {
                applyTouchControls()
            }
        }
    }

    private fun injectTouchHud() {
        val raw = getPreferences(Context.MODE_PRIVATE).getString("touch_controls_json", "") ?: defaultTouchControlsJson()
        val escaped = escapeJs(raw)
        val script = """
            (function() {
              var old = document.getElementById('rpgrtl-hud');
              if (old) old.remove();
              var config;
              try { config = JSON.parse('$escaped'); } catch (e) { config = null; }
              if (!config || config.enabled === false || !Array.isArray(config.buttons)) return;
              var root = document.createElement('div');
              root.id = 'rpgrtl-hud';
              root.style.cssText = 'position:fixed;inset:0;z-index:2147483647;pointer-events:none;font-family:sans-serif;';
              var style = document.createElement('style');
              style.textContent = [
                '#rpgrtl-hud .btn,#rpgrtl-hud .joy{position:absolute;pointer-events:auto;touch-action:none;user-select:none;-webkit-user-select:none;}',
                '#rpgrtl-hud .btn{display:flex;align-items:center;justify-content:center;border:1px solid rgba(0,255,255,.62);background:rgba(12,18,26,.72);color:#fff;font-weight:800;border-radius:8px;box-shadow:0 5px 16px rgba(0,0,0,.28);}',
                '#rpgrtl-hud .joy{border-radius:50%;border:2px solid rgba(0,255,255,.52);background:rgba(12,18,26,.34);}',
                '#rpgrtl-hud .thumb{position:absolute;left:50%;top:50%;border-radius:50%;border:2px solid rgba(0,255,255,.85);background:rgba(0,102,255,.62);}'
              ].join('');
              document.head.appendChild(style);

              function mkEvent(type, mapped) {
                return new KeyboardEvent(type, {key:mapped[0], code:mapped[1], keyCode:mapped[2], which:mapped[2], bubbles:true, cancelable:true});
              }
              function map(code) {
                code = Number(code);
                if (code === 19) return ['ArrowUp','ArrowUp',38];
                if (code === 20) return ['ArrowDown','ArrowDown',40];
                if (code === 21) return ['ArrowLeft','ArrowLeft',37];
                if (code === 22) return ['ArrowRight','ArrowRight',39];
                if (code === 4) return ['Escape','Escape',27];
                if (code === 59) return ['Shift','ShiftLeft',16];
                if (code === 113) return ['Control','ControlLeft',17];
                if (code === 62) return [' ','Space',32];
                return ['Enter','Enter',13];
              }
              function send(type, code) {
                var evt = mkEvent(type, map(code));
                document.dispatchEvent(evt);
                window.dispatchEvent(evt);
              }
              var activeDir = null;
              function releaseDir() { if (activeDir != null) { send('keyup', activeDir); activeDir = null; } }
              function setDir(code) { if (activeDir === code) return; releaseDir(); activeDir = code; send('keydown', code); }

              config.buttons.forEach(function(item) {
                if (!item || item.enabled === false) return;
                var x = Math.max(0.02, Math.min(0.98, Number(item.x) || 0.5));
                var y = Math.max(0.04, Math.min(0.96, Number(item.y) || 0.5));
                var size = Math.max(34, Math.min(180, Number(item.size) || 58));
                var opacity = Math.max(0.18, Math.min(1, Number(item.opacity) || 0.68));
                if (item.kind === 'joystick' || item.id === 'joystick') {
                  var joy = document.createElement('div');
                  joy.className = 'joy';
                  joy.style.width = size + 'px';
                  joy.style.height = size + 'px';
                  joy.style.left = (x * 100) + '%';
                  joy.style.top = (y * 100) + '%';
                  joy.style.opacity = opacity;
                  joy.style.transform = 'translate(-50%,-50%)';
                  var thumb = document.createElement('div');
                  var thumbSize = Math.max(42, Math.round(size * 0.42));
                  thumb.className = 'thumb';
                  thumb.style.width = thumbSize + 'px';
                  thumb.style.height = thumbSize + 'px';
                  thumb.style.marginLeft = -(thumbSize / 2) + 'px';
                  thumb.style.marginTop = -(thumbSize / 2) + 'px';
                  joy.appendChild(thumb);
                  var pointer = null;
                  var rect = null;
                  function move(ev) {
                    if (!rect) return;
                    var cx = rect.left + rect.width / 2;
                    var cy = rect.top + rect.height / 2;
                    var dx = ev.clientX - cx;
                    var dy = ev.clientY - cy;
                    var len = Math.sqrt(dx*dx + dy*dy);
                    var max = size * 0.34;
                    var nx = dx;
                    var ny = dy;
                    if (len > max) { nx = dx / len * max; ny = dy / len * max; }
                    thumb.style.transform = 'translate(' + nx + 'px,' + ny + 'px)';
                    if (Math.abs(dx) < 16 && Math.abs(dy) < 16) { releaseDir(); return; }
                    if (Math.abs(dx) > Math.abs(dy)) setDir(dx > 0 ? 22 : 21); else setDir(dy > 0 ? 20 : 19);
                  }
                  function reset() { pointer = null; rect = null; thumb.style.transform = 'translate(0,0)'; releaseDir(); }
                  joy.addEventListener('pointerdown', function(ev) { pointer = ev.pointerId; rect = joy.getBoundingClientRect(); joy.setPointerCapture(pointer); move(ev); });
                  joy.addEventListener('pointermove', function(ev) { if (ev.pointerId === pointer) move(ev); });
                  joy.addEventListener('pointerup', function(ev) { if (ev.pointerId === pointer) reset(); });
                  joy.addEventListener('pointercancel', reset);
                  root.appendChild(joy);
                } else {
                  var btn = document.createElement('div');
                  btn.className = 'btn';
                  btn.textContent = item.label || 'BTN';
                  btn.style.width = size + 'px';
                  btn.style.height = size + 'px';
                  btn.style.left = (x * 100) + '%';
                  btn.style.top = (y * 100) + '%';
                  btn.style.opacity = opacity;
                  btn.style.transform = 'translate(-50%,-50%)';
                  btn.addEventListener('pointerdown', function() { send('keydown', item.keyCode); });
                  btn.addEventListener('pointerup', function() { send('keyup', item.keyCode); });
                  btn.addEventListener('pointercancel', function() { send('keyup', item.keyCode); });
                  root.appendChild(btn);
                }
              });
              document.body.appendChild(root);
            })();
        """.trimIndent()
        binding.gameWebView.evaluateJavascript(script, null)
    }

    private fun clearTouchControls() {
        touchButtonViews.forEach { view ->
            binding.root.removeView(view)
        }
        touchButtonViews.clear()
    }

    private fun dispatchKeyToGame(keyCode: Int, action: Int) {
        val event = KeyEvent(System.currentTimeMillis(), System.currentTimeMillis(), action, keyCode, 0)
        binding.gameWebView.requestFocus()
        binding.gameWebView.dispatchKeyEvent(event)
        val type = if (action == KeyEvent.ACTION_DOWN) "keydown" else "keyup"
        val key = jsKeyForKeyCode(keyCode)
        val code = jsCodeForKeyCode(keyCode)
        val jsKeyCode = jsKeyCodeForAndroidKeyCode(keyCode)
        val script = """
            (function(){
              var event = new KeyboardEvent('$type', {
                key: '$key',
                code: '$code',
                keyCode: $jsKeyCode,
                which: $jsKeyCode,
                bubbles: true,
                cancelable: true
              });
              document.dispatchEvent(event);
              window.dispatchEvent(event);
            })();
        """.trimIndent()
        binding.gameWebView.evaluateJavascript(script, null)
    }

    private fun jsKeyForKeyCode(keyCode: Int): String {
        return when (keyCode) {
            KeyEvent.KEYCODE_DPAD_UP -> "ArrowUp"
            KeyEvent.KEYCODE_DPAD_DOWN -> "ArrowDown"
            KeyEvent.KEYCODE_DPAD_LEFT -> "ArrowLeft"
            KeyEvent.KEYCODE_DPAD_RIGHT -> "ArrowRight"
            KeyEvent.KEYCODE_ENTER -> "Enter"
            KeyEvent.KEYCODE_BACK, KeyEvent.KEYCODE_ESCAPE -> "Escape"
            KeyEvent.KEYCODE_SHIFT_LEFT, KeyEvent.KEYCODE_SHIFT_RIGHT -> "Shift"
            KeyEvent.KEYCODE_CTRL_LEFT, KeyEvent.KEYCODE_CTRL_RIGHT -> "Control"
            KeyEvent.KEYCODE_SPACE -> " "
            KeyEvent.KEYCODE_Q -> "q"
            KeyEvent.KEYCODE_W -> "w"
            KeyEvent.KEYCODE_E -> "e"
            KeyEvent.KEYCODE_R -> "r"
            KeyEvent.KEYCODE_A -> "a"
            KeyEvent.KEYCODE_S -> "s"
            KeyEvent.KEYCODE_D -> "d"
            KeyEvent.KEYCODE_Z -> "z"
            KeyEvent.KEYCODE_X -> "x"
            KeyEvent.KEYCODE_C -> "c"
            KeyEvent.KEYCODE_TAB -> "Tab"
            KeyEvent.KEYCODE_F5 -> "F5"
            KeyEvent.KEYCODE_F12 -> "F12"
            else -> "Enter"
        }
    }

    private fun jsCodeForKeyCode(keyCode: Int): String {
        return when (keyCode) {
            KeyEvent.KEYCODE_DPAD_UP -> "ArrowUp"
            KeyEvent.KEYCODE_DPAD_DOWN -> "ArrowDown"
            KeyEvent.KEYCODE_DPAD_LEFT -> "ArrowLeft"
            KeyEvent.KEYCODE_DPAD_RIGHT -> "ArrowRight"
            KeyEvent.KEYCODE_ENTER -> "Enter"
            KeyEvent.KEYCODE_BACK, KeyEvent.KEYCODE_ESCAPE -> "Escape"
            KeyEvent.KEYCODE_SHIFT_LEFT, KeyEvent.KEYCODE_SHIFT_RIGHT -> "ShiftLeft"
            KeyEvent.KEYCODE_CTRL_LEFT, KeyEvent.KEYCODE_CTRL_RIGHT -> "ControlLeft"
            KeyEvent.KEYCODE_SPACE -> "Space"
            KeyEvent.KEYCODE_Q -> "KeyQ"
            KeyEvent.KEYCODE_W -> "KeyW"
            KeyEvent.KEYCODE_E -> "KeyE"
            KeyEvent.KEYCODE_R -> "KeyR"
            KeyEvent.KEYCODE_A -> "KeyA"
            KeyEvent.KEYCODE_S -> "KeyS"
            KeyEvent.KEYCODE_D -> "KeyD"
            KeyEvent.KEYCODE_Z -> "KeyZ"
            KeyEvent.KEYCODE_X -> "KeyX"
            KeyEvent.KEYCODE_C -> "KeyC"
            KeyEvent.KEYCODE_TAB -> "Tab"
            KeyEvent.KEYCODE_F5 -> "F5"
            KeyEvent.KEYCODE_F12 -> "F12"
            else -> "Enter"
        }
    }

    private fun jsKeyCodeForAndroidKeyCode(keyCode: Int): Int {
        return when (keyCode) {
            KeyEvent.KEYCODE_DPAD_UP -> 38
            KeyEvent.KEYCODE_DPAD_DOWN -> 40
            KeyEvent.KEYCODE_DPAD_LEFT -> 37
            KeyEvent.KEYCODE_DPAD_RIGHT -> 39
            KeyEvent.KEYCODE_ENTER -> 13
            KeyEvent.KEYCODE_BACK, KeyEvent.KEYCODE_ESCAPE -> 27
            KeyEvent.KEYCODE_SHIFT_LEFT, KeyEvent.KEYCODE_SHIFT_RIGHT -> 16
            KeyEvent.KEYCODE_CTRL_LEFT, KeyEvent.KEYCODE_CTRL_RIGHT -> 17
            KeyEvent.KEYCODE_SPACE -> 32
            KeyEvent.KEYCODE_Q -> 81
            KeyEvent.KEYCODE_W -> 87
            KeyEvent.KEYCODE_E -> 69
            KeyEvent.KEYCODE_R -> 82
            KeyEvent.KEYCODE_A -> 65
            KeyEvent.KEYCODE_S -> 83
            KeyEvent.KEYCODE_D -> 68
            KeyEvent.KEYCODE_Z -> 90
            KeyEvent.KEYCODE_X -> 88
            KeyEvent.KEYCODE_C -> 67
            KeyEvent.KEYCODE_TAB -> 9
            KeyEvent.KEYCODE_F5 -> 116
            KeyEvent.KEYCODE_F12 -> 123
            else -> 13
        }
    }

    fun openGameAsset(relativePath: String, requestHeaders: Map<String, String> = emptyMap()): WebResourceResponse? {
        val root = gameTreeRoot ?: return null
        val normalized = normalizeGamePath(relativePath)
        val resolved = resolveGameAssetWithAudioFallback(root, normalized) ?: return null
        val file = resolved.first
        val resolvedPath = resolved.second
        if (!file.isFile) return null
        translatedGameAsset(resolvedPath)?.let { return it }
        val stream = contentResolver.openInputStream(file.uri) ?: return null
        if (isHtmlPath(normalized)) {
            val html = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            return WebResourceResponse(
                mimeTypeForPath(resolvedPath),
                "UTF-8",
                200,
                "OK",
                cacheHeadersForPath(resolvedPath),
                ByteArrayInputStream(sanitizeGameHtml(html).toByteArray(Charsets.UTF_8))
            )
        }
        if (isRangeFriendlyAsset(resolvedPath)) {
            return rangedGameAssetResponse(file, resolvedPath, requestHeaders) ?: WebResourceResponse(
                mimeTypeForPath(resolvedPath),
                null,
                200,
                "OK",
                cacheHeadersForPath(resolvedPath) + mapOf(
                    "Accept-Ranges" to "bytes",
                    "Content-Length" to file.length().coerceAtLeast(0L).toString()
                ),
                stream
            )
        }
        return WebResourceResponse(
            mimeTypeForPath(resolvedPath),
            "UTF-8",
            200,
            "OK",
            cacheHeadersForPath(resolvedPath),
            stream
        )
    }

    private fun resolveGameAssetWithAudioFallback(root: DocumentFile, path: String): Pair<DocumentFile, String>? {
        findGameDocument(root, path)?.let { return it to path }
        val ext = path.substringAfterLast('.', "").lowercase()
        val base = path.substringBeforeLast('.', path)
        val alternatives = when (ext) {
            "ogg" -> listOf("$base.m4a", "$base.mp3", "$base.wav")
            "m4a" -> listOf("$base.ogg", "$base.mp3", "$base.wav")
            "mp3" -> listOf("$base.ogg", "$base.m4a", "$base.wav")
            else -> emptyList()
        }
        for (candidate in alternatives) {
            findGameDocument(root, candidate)?.let { return it to candidate }
        }
        return null
    }

    private fun isRangeFriendlyAsset(path: String): Boolean {
        return when (path.substringAfterLast('.', "").lowercase()) {
            "m4a", "mp3", "ogg", "wav", "webm", "mp4", "m4v" -> true
            else -> false
        }
    }

    private fun rangedGameAssetResponse(file: DocumentFile, path: String, requestHeaders: Map<String, String>): WebResourceResponse? {
        val total = file.length().coerceAtLeast(0L)
        val rangeHeader = requestHeaders.entries.firstOrNull { it.key.equals("Range", ignoreCase = true) }?.value ?: return null
        val match = Regex("bytes=(\\d*)-(\\d*)").find(rangeHeader.trim()) ?: return null
        val startText = match.groupValues[1]
        val endText = match.groupValues[2]
        if (total <= 0L || startText.isBlank()) return null
        val start = startText.toLongOrNull()?.coerceIn(0L, total - 1) ?: return null
        val requestedEnd = endText.toLongOrNull() ?: (total - 1)
        val end = requestedEnd.coerceIn(start, total - 1)
        val length = end - start + 1
        val pfd = runCatching { contentResolver.openFileDescriptor(file.uri, "r") }.getOrNull()
        val input: InputStream = if (pfd != null) {
            val fis = java.io.FileInputStream(pfd.fileDescriptor)
            runCatching { fis.channel.position(start) }
            fis
        } else {
            val stream = contentResolver.openInputStream(file.uri) ?: return null
            skipFully(stream, start)
            stream
        }
        val limited = object : java.io.FilterInputStream(input) {
            private var remaining = length
            override fun read(): Int {
                if (remaining <= 0) return -1
                val value = super.read()
                if (value >= 0) remaining -= 1
                return value
            }
            override fun read(buffer: ByteArray, offset: Int, count: Int): Int {
                if (remaining <= 0) return -1
                val max = minOf(count.toLong(), remaining).toInt()
                val read = super.read(buffer, offset, max)
                if (read > 0) remaining -= read.toLong()
                return read
            }
            override fun close() {
                try {
                    super.close()
                } finally {
                    runCatching { pfd?.close() }
                }
            }
        }
        return WebResourceResponse(
            mimeTypeForPath(path),
            null,
            206,
            "Partial Content",
            cacheHeadersForPath(path) + mapOf(
                "Accept-Ranges" to "bytes",
                "Content-Range" to "bytes $start-$end/$total",
                "Content-Length" to length.toString()
            ),
            limited
        )
    }

    private fun skipFully(input: InputStream, bytes: Long) {
        var remaining = bytes
        while (remaining > 0) {
            val skipped = input.skip(remaining)
            if (skipped > 0) {
                remaining -= skipped
            } else if (input.read() >= 0) {
                remaining -= 1
            } else {
                break
            }
        }
    }

    private fun isHtmlPath(path: String): Boolean {
        return path.endsWith(".html", ignoreCase = true) || path.endsWith(".htm", ignoreCase = true)
    }

    private fun sanitizeGameHtml(html: String): String {
        val cleaned = html
            .replace("MTool", "RPGRenPyLocalizer", ignoreCase = true)
            .replace("\u5982\u679c\u4e00\u76f4\u663e\u793a\u8fd9\u4e2a\u9875\u9762, \u8bf7\u52a0\u5165 Discord \u56de\u62a5\u95ee\u9898.", "If loading stays here, return to the tool panel and relaunch.")
            .replace("If this page keeps displaying, please join our Discord to report the problem.", "If this page keeps displaying, return to the tool page and relaunch the game.")
            .replace("Click To Exit", "Return to tool panel")
        val patch = "<script>${rpgMakerAudioCompatibilityPatch()}</script>"
        return when {
            cleaned.contains("</head>", ignoreCase = true) -> cleaned.replaceFirst(Regex("</head>", RegexOption.IGNORE_CASE), "$patch</head>")
            cleaned.contains("<body", ignoreCase = true) -> cleaned.replaceFirst(Regex("<body", RegexOption.IGNORE_CASE), "$patch<body")
            else -> patch + cleaned
        }
    }

    private fun rpgMakerAudioCompatibilityPatch(): String {
        return """
            (function(){
              if (window.__rpgrtlAudioPatch) return;
              window.__rpgrtlAudioPatch = true;
              var rawAlert = window.alert;
              window.alert = function(message) {
                var text = String(message || '');
                if (/fail(ed)? to load audio|now loading the default audio|\u65e0\u6cd5\u52a0\u8f7d\u97f3\u9891|\u9ed8\u8ba4\u97f3\u9891/i.test(text)) {
                  console.warn('[RPGRenPyLocalizer] suppressed RPGMaker audio alert: ' + text);
                  return;
                }
                return rawAlert.apply(this, arguments);
              };
              function patchAudioManager(){
                try {
                  if (window.Utils) {
                    if (typeof Utils.canPlayOgg === 'function') Utils.canPlayOgg = function(){ return true; };
                    if (typeof Utils.canPlayM4A === 'function') Utils.canPlayM4A = function(){ return false; };
                  }
                  if (window.AudioManager && !AudioManager.__rpgrtlPatched) {
                    AudioManager.__rpgrtlPatched = true;
                    AudioManager.audioFileExt = function(){ return '.ogg'; };
                    AudioManager.checkErrors = function(){};
                    if (AudioManager.checkWebAudioError) AudioManager.checkWebAudioError = function(){};
                  }
                  if (window.WebAudio && WebAudio.prototype && !WebAudio.prototype.__rpgrtlPatched) {
                    WebAudio.prototype.__rpgrtlPatched = true;
                    WebAudio.prototype._onError = function(){
                      this._hasError = false;
                      this._autoPlay = false;
                      this._isLoading = false;
                      console.warn('[RPGRenPyLocalizer] suppressed failed audio fallback: ' + (this._url || ''));
                    };
                  }
                  if (window.Graphics && !Graphics.__rpgrtlAudioPatch) {
                    Graphics.__rpgrtlAudioPatch = true;
                    var rawPrintError = Graphics.printError;
                    Graphics.printError = function(name, message) {
                      var text = String(name || '') + ' ' + String(message || '');
                      if (/fail(ed)? to load audio|now loading the default audio|\u65e0\u6cd5\u52a0\u8f7d\u97f3\u9891|\u9ed8\u8ba4\u97f3\u9891/i.test(text)) return;
                      return rawPrintError && rawPrintError.apply(this, arguments);
                    };
                  }
                } catch (e) { console.warn('[RPGRenPyLocalizer] audio patch error', e); }
              }
              patchAudioManager();
              var tries = 0;
              var timer = setInterval(function(){ patchAudioManager(); if (++tries > 120) clearInterval(timer); }, 250);
            })();
        """.trimIndent().replace("</script", "<" + "/script")
    }

    private fun translatedGameAsset(path: String): WebResourceResponse? {
        if (!shouldInjectTranslations()) return null
        if (!path.endsWith(".json", ignoreCase = true)) return null
        val translated = readTranslationOverride(path) ?: return null
        return WebResourceResponse(
            mimeTypeForPath(path),
            "UTF-8",
            200,
            "OK",
            cacheHeadersForPath(path),
            ByteArrayInputStream(translated.toByteArray(Charsets.UTF_8))
        )
    }

    private fun cacheHeadersForPath(path: String): Map<String, String> {
        val noCache = path.endsWith(".json", ignoreCase = true)
        return if (noCache) {
            mapOf("Cache-Control" to "no-cache")
        } else {
            mapOf("Cache-Control" to "public, max-age=604800, immutable")
        }
    }

    fun injectGameCompatibilityPatch(view: WebView?) {
        val raw = getPreferences(Context.MODE_PRIVATE).getString("launch_settings_json", "") ?: ""
        val settings = try { if (raw.isBlank()) JSONObject() else JSONObject(raw) } catch (_: Throwable) { JSONObject() }
        if (settings.optString("renderMode", "fast") != "compat") return
        val script = """
            (function(){
              if (window.__rpgrtlWebglCompat) return;
              window.__rpgrtlWebglCompat = true;
              var oldGetContext = HTMLCanvasElement.prototype.getContext;
              HTMLCanvasElement.prototype.getContext = function(type, attrs) {
                if (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl') {
                  attrs = Object.assign({}, attrs || {}, {
                    alpha: false,
                    antialias: false,
                    premultipliedAlpha: true,
                    preserveDrawingBuffer: false,
                    powerPreference: 'high-performance',
                    failIfMajorPerformanceCaveat: false
                  });
                }
                return oldGetContext.call(this, type, attrs);
              };
              console.warn('[PERF] WebGL compat patch installed');
            })();
        """.trimIndent()
        view?.evaluateJavascript(script, null)
    }

    private fun shouldInjectTranslations(): Boolean {
        val raw = getPreferences(Context.MODE_PRIVATE).getString("launch_settings_json", "") ?: ""
        val settings = try { if (raw.isBlank()) JSONObject() else JSONObject(raw) } catch (_: Throwable) { JSONObject() }
        return settings.optString("renderMode", "fast") == "compat" && settings.optBoolean("translationInject", true)
    }

    private fun readTranslationOverride(path: String): String? {
        val root = lastTreeUri?.let { DocumentFile.fromTreeUri(this, it) } ?: return null
        val dir = root.findFile(".rpgrtl_android")?.findFile("translation") ?: return null
        val safeName = path.replace("/", "__")
        val file = dir.findFile(safeName) ?: dir.findFile("$safeName.json") ?: return null
        return contentResolver.openInputStream(file.uri)?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }
    }

    private fun normalizeGamePath(path: String): String {
        val cleaned = path.substringBefore("?").substringBefore("#").trimStart('/')
        val parts = mutableListOf<String>()
        cleaned.split('/').forEach { part ->
            when {
                part.isBlank() || part == "." -> Unit
                part == ".." -> if (parts.isNotEmpty()) parts.removeAt(parts.lastIndex)
                else -> parts.add(part)
            }
        }
        return parts.joinToString("/")
    }

    private fun findDocumentByPath(root: DocumentFile, path: String): DocumentFile? {
        val indexed = gameFileIndex[path.lowercase()]
        if (indexed != null) {
            gameAssetCache[path] = indexed
            return indexed
        }
        val cachedPath = gamePathIndex[path.lowercase()]
        if (cachedPath != null && cachedPath != path) {
            findDocumentByPath(root, cachedPath)?.let {
                gameAssetCache[path] = it
                return it
            }
        }
        gameAssetCache[path]?.let { return it }
        if (gameAssetCache.containsKey(path)) return null
        if (path.isBlank()) return root
        var current: DocumentFile = root
        val traversed = mutableListOf<String>()
        path.split('/').forEach { segment ->
            val dirKey = traversed.joinToString("/")
            val files = gameDirectoryCache.getOrPut(dirKey) { current.listFiles().toList() }
            val next = files.firstOrNull { it.name == segment }
                ?: files.firstOrNull { it.name.equals(segment, ignoreCase = true) }
                ?: run {
                    gameAssetCache[path] = null
                    return null
                }
            current = next
            traversed.add(segment)
        }
        gameAssetCache[path] = current
        return current
    }

    private fun buildGameFileIndex(root: DocumentFile, uri: Uri? = lastTreeUri) {
        Thread {
            val index = ConcurrentHashMap<String, DocumentFile>()
            val pathIndex = ConcurrentHashMap<String, String>()
            try {
                root.listFiles().forEach { child ->
                    val name = child.name ?: return@forEach
                    index[name.lowercase()] = child
                    pathIndex[name.lowercase()] = name
                }
                gameFileIndex = index
            } catch (_: Throwable) {}

            fun walk(node: DocumentFile, prefix: String, depth: Int) {
                if (depth > 8) return
                node.listFiles().forEach { child ->
                    val name = child.name ?: return@forEach
                    val path = if (prefix.isBlank()) name else "$prefix/$name"
                    index[path.lowercase()] = child
                    pathIndex[path.lowercase()] = path
                    if (child.isDirectory) walk(child, path, depth + 1)
                }
            }
            try {
                walk(root, "", 0)
                synchronized(gamePathIndex) {
                    gamePathIndex.clear()
                    gamePathIndex.putAll(pathIndex)
                }
                gameFileIndex = index
                saveGamePathIndex(pathIndex, uri)
                notifyWeb("File index ready: ${index.size} items")
            } catch (_: Throwable) {
                if (gameFileIndex.isEmpty()) gameFileIndex = emptyMap()
            }
        }.start()
    }

    fun androidLaunchGame(backend: String): String {
        val normalized = backend.lowercase()
        if (normalized.contains("wine") || normalized.contains("ren") || normalized.contains("exe") ||
            normalized.contains("windows") || normalized.contains("compatible")
        ) {
            val targetExe = lastExeUri ?: findSelectedExeUri()
            val title = externalGameTitle.ifBlank { targetExe?.let { displayNameForUri(it) }.orEmpty() }
            return WineEngineBridge(this).launch(gameUri = targetExe, title = title, gameTreeUri = lastTreeUri).toString()
        }
        runOnUiThread {
            when {
                normalized.contains("ren") -> launchRenpyGame()
                normalized.contains("exe") ||
                    normalized.contains("windows") ||
                    normalized.contains("wine") ||
                    normalized.contains("compatible") -> launchExeWithExternalRunner()
                else -> launchSelectedGame()
            }
        }
        return JSONObject()
            .put("ok", true)
            .put("backend", normalized.ifBlank { "rpgmaker-webview" })
            .toString()
    }

    private fun restoreGamePathIndex(uri: Uri?) {
        val uriText = uri?.toString() ?: return
        val prefs = getPreferences(Context.MODE_PRIVATE)
        if (prefs.getString("file_index_uri", "") != uriText) return
        val time = prefs.getLong("file_index_time", 0)
        if (System.currentTimeMillis() - time > 10 * 60 * 1000) return
        val raw = prefs.getString("file_index_cache", "") ?: return
        if (raw.isBlank()) return
        try {
            val obj = JSONObject(raw)
            synchronized(gamePathIndex) {
                gamePathIndex.clear()
                obj.keys().forEach { key -> gamePathIndex[key] = obj.optString(key) }
            }
            notifyWeb("Cached file index loaded: ${gamePathIndex.size} items")
        } catch (_: Throwable) {
            gamePathIndex.clear()
        }
    }

    private fun saveGamePathIndex(index: Map<String, String>, uri: Uri?) {
        if (uri == null || index.isEmpty()) return
        val obj = JSONObject()
        index.forEach { (key, value) -> obj.put(key, value) }
        getPreferences(Context.MODE_PRIVATE)
            .edit()
            .putString("file_index_uri", uri.toString())
            .putString("file_index_cache", obj.toString())
            .putLong("file_index_time", System.currentTimeMillis())
            .apply()
    }

    private fun findDocumentByPathNoCache(root: DocumentFile, path: String): DocumentFile? {
        if (path.isBlank()) return root
        var current: DocumentFile = root
        path.split('/').forEach { segment ->
            val next = current.listFiles().firstOrNull { it.name == segment }
                ?: current.listFiles().firstOrNull { it.name.equals(segment, ignoreCase = true) }
                ?: return null
            current = next
        }
        return current
    }

    private fun findGameDocument(root: DocumentFile, path: String): DocumentFile? {
        findDocumentByPath(root, path)?.let { return it }
        val raw = getPreferences(Context.MODE_PRIVATE).getString("launch_settings_json", "") ?: ""
        val fallbackEnabled = try {
            if (raw.isBlank()) true else JSONObject(raw).optBoolean("resourceFallback", true)
        } catch (_: Throwable) {
            true
        }
        if (!fallbackEnabled || gameVirtualBase.isBlank() || path.startsWith("$gameVirtualBase/")) {
            return null
        }
        return findDocumentByPath(root, "$gameVirtualBase/$path")
    }

    private fun mimeTypeForPath(path: String): String {
        return when (path.substringAfterLast('.', "").lowercase()) {
            "html", "htm" -> "text/html"
            "js", "mjs" -> "application/javascript"
            "json" -> "application/json"
            "css" -> "text/css"
            "png" -> "image/png"
            "jpg", "jpeg" -> "image/jpeg"
            "webp" -> "image/webp"
            "gif" -> "image/gif"
            "svg" -> "image/svg+xml"
            "ogg" -> "audio/ogg"
            "m4a" -> "audio/mp4"
            "mp3" -> "audio/mpeg"
            "wav" -> "audio/wav"
            "ttf" -> "font/ttf"
            "otf" -> "font/otf"
            "woff" -> "font/woff"
            "woff2" -> "font/woff2"
            else -> "application/octet-stream"
        }
    }

    private fun copyDocumentTree(source: DocumentFile, target: File) {
        if (!target.exists()) target.mkdirs()
        source.listFiles().forEach { child ->
            val safeName = child.name ?: return@forEach
            val destination = File(target, safeName)
            if (child.isDirectory) {
                copyDocumentTree(child, destination)
            } else if (child.isFile) {
                contentResolver.openInputStream(child.uri)?.use { input ->
                    destination.parentFile?.mkdirs()
                    destination.outputStream().use { output ->
                        input.copyTo(output)
                    }
                }
            }
        }
    }

    private fun copyDocumentTreeWithProgress(source: DocumentFile, target: File, label: String) {
        val stats = countDocumentTree(source)
        val copiedFiles = AtomicInteger(0)
        val copiedBytes = AtomicLong(0)
        var lastNotify = 0L
        fun copyNode(node: DocumentFile, destination: File) {
            val safeName = node.name ?: return
            val out = File(destination, safeName)
            if (node.isDirectory) {
                out.mkdirs()
                node.listFiles().forEach { copyNode(it, out) }
            } else if (node.isFile) {
                contentResolver.openInputStream(node.uri)?.use { input ->
                    out.parentFile?.mkdirs()
                    out.outputStream().use { output ->
                        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                        while (true) {
                            val read = input.read(buffer)
                            if (read <= 0) break
                            output.write(buffer, 0, read)
                            copiedBytes.addAndGet(read.toLong())
                            val now = System.currentTimeMillis()
                            if (now - lastNotify > 900) {
                                lastNotify = now
                                notifyWeb("Copying $label: ${copiedFiles.get()}/${stats.files} files, ${formatBytes(copiedBytes.get())}/${formatBytes(stats.bytes)}")
                            }
                        }
                    }
                }
                copiedFiles.incrementAndGet()
            }
        }
        if (!target.exists()) target.mkdirs()
        source.listFiles().forEach { copyNode(it, target) }
        notifyWeb("$label copy done: ${copiedFiles.get()} files, ${formatBytes(copiedBytes.get())}")
    }

    private data class TreeStats(val files: Int, val dirs: Int, val bytes: Long)

    private fun countDocumentTree(root: DocumentFile): TreeStats {
        var files = 0
        var dirs = 0
        var bytes = 0L
        fun walk(node: DocumentFile) {
            node.listFiles().forEach { child ->
                if (child.isDirectory) {
                    dirs += 1
                    walk(child)
                } else if (child.isFile) {
                    files += 1
                    bytes += child.length().coerceAtLeast(0L)
                }
            }
        }
        walk(root)
        return TreeStats(files, dirs, bytes)
    }

    private fun formatBytes(value: Long): String {
        if (value < 1024) return "${value}B"
        val kb = value / 1024.0
        if (kb < 1024) return String.format("%.1fKB", kb)
        val mb = kb / 1024.0
        if (mb < 1024) return String.format("%.1fMB", mb)
        return String.format("%.2fGB", mb / 1024.0)
    }

    private fun scanGameTree(root: DocumentFile, uri: Uri): JSONObject {
        val highlights = JSONArray()
        val stats = JSONObject()
        var fileCount = 0
        var dirCount = 0
        var mapCount = 0
        var dataFileCount = 0
        var scriptCount = 0
        var actorCount = 0
        var itemCount = 0
        var textHintCount = 0
        var firstExe = ""
        var firstExeUri: Uri? = null
        var iconPngUri: Uri? = null
        var rpgEntry = ""
        var renpyEntry = ""
        var hasRpgData = false
        var hasRenpyGame = false

        fun addHighlight(label: String, value: String) {
            highlights.put(JSONObject().put("label", label).put("value", value))
        }

        fun inspectDataDir(dataDir: DocumentFile?, prefix: String) {
            if (dataDir == null || !dataDir.isDirectory) return
            hasRpgData = true
            addHighlight("RPG Maker data", prefix)
            dataDir.listFiles().forEach { file ->
                val name = file.name ?: return@forEach
                if (!file.isFile || !name.endsWith(".json", ignoreCase = true)) return@forEach
                dataFileCount += 1
                textHintCount += 1
                val lower = name.lowercase()
                if (lower.startsWith("map") && lower != "mapinfos.json") mapCount += 1
                if (lower == "actors.json") actorCount = 1
                if (lower == "items.json") itemCount = 1
            }
        }

        fun maybeIconPng(name: String, file: DocumentFile) {
            if (iconPngUri != null || !file.isFile) return
            val lower = name.lowercase()
            if (lower == "icon.png" || lower == "icon.ico" || lower == "game.png" ||
                lower == "cover.png" || lower == "logo.png" || lower.endsWith("-icon.png")
            ) {
                iconPngUri = file.uri
            }
        }

        fun walk(node: DocumentFile, relative: String, depth: Int) {
            // Keep walking deep enough to find exe/icons even after engine is known.
            if (depth > 4 || fileCount > 800) return
            val children = node.listFiles()
            children.forEach { child ->
                val name = child.name ?: return@forEach
                val path = if (relative.isBlank()) name else "$relative/$name"
                if (child.isDirectory) {
                    dirCount += 1
                    if (name.equals("www", ignoreCase = true)) {
                        addHighlight("RPG Maker folder", path)
                        val data = child.findFile("data")
                        inspectDataDir(data, "$path/data")
                        child.findFile("index.html")?.let { index ->
                            if (rpgEntry.isBlank() && isValidRpgMakerEntry(child, index)) {
                                rpgEntry = "$path/index.html"
                                addHighlight("MV/MZ Web entry", "$path/index.html")
                            } else if (isThirdPartyToolLoader(index)) {
                                addHighlight("Ignored tool loader", "$path/index.html")
                            }
                        }
                        // Common RPG Maker icon paths
                        child.findFile("icon")?.findFile("icon.png")?.let { maybeIconPng("icon.png", it) }
                        child.findFile("icon.png")?.let { maybeIconPng("icon.png", it) }
                    }
                    if (name.equals("data", ignoreCase = true) && child.findFile("System.json") != null) {
                        inspectDataDir(child, path)
                    }
                    if (name.equals("game", ignoreCase = true)) {
                        hasRenpyGame = true
                        addHighlight("RenPy game folder", path)
                    }
                    if (name.equals("icon", ignoreCase = true) || name.equals("icons", ignoreCase = true)) {
                        child.findFile("icon.png")?.let { maybeIconPng("icon.png", it) }
                    }
                    walk(child, path, depth + 1)
                } else if (child.isFile) {
                    fileCount += 1
                    val lower = name.lowercase()
                    maybeIconPng(name, child)
                    if (firstExe.isBlank() && lower.endsWith(".exe")) {
                        firstExe = path
                        firstExeUri = child.uri
                        addHighlight("Executable", path)
                    }
                    if (rpgEntry.isBlank() && lower == "index.html" && (relative.equals("www", true) || path.equals("index.html", true))) {
                        val base = if (relative.equals("www", true)) node else root
                        if (isValidRpgMakerEntry(base, child)) {
                            rpgEntry = path
                            addHighlight("MV/MZ Web entry", path)
                        } else if (isThirdPartyToolLoader(child)) {
                            addHighlight("Ignored tool loader", path)
                        }
                    }
                    if (renpyEntry.isBlank() && lower == "index.html" && !relative.equals("www", true)) {
                        renpyEntry = path
                    }
                    if (lower.endsWith(".rpy") || lower.endsWith(".rpyc") || lower.endsWith(".rpa")) {
                        scriptCount += 1
                        hasRenpyGame = true
                    }
                    if (lower.endsWith(".json") || lower.endsWith(".rpy") || lower.endsWith(".txt")) {
                        textHintCount += 1
                    }
                }
            }
        }
        walk(root, "", 0)

        // Prefer real exe from tree if path-only scan missed DocumentFile handle.
        if (firstExeUri == null) {
            findFirstExe(root)?.let {
                firstExeUri = it.uri
                if (firstExe.isBlank()) firstExe = it.name.orEmpty()
            }
        }

        val engine = when {
            rpgEntry.isNotBlank() && hasRpgData -> "RPG Maker MV/MZ"
            hasRenpyGame -> "Ren'Py"
            firstExe.isNotBlank() -> "Windows exe / compatible runner"
            else -> "Unknown"
        }
        val advice = when (engine) {
            "RPG Maker MV/MZ" -> "RPG Maker MV/MZ entry found. On-demand mode is available."
            "Ren'Py" -> if (renpyEntry.isNotBlank()) "RenPy Web entry found." else "RenPy resources found, but no Web entry was found."
            "Windows exe / compatible runner" -> "Android cannot run exe natively. Use a compatible runner."
            else -> "No directly runnable entry was found."
        }

        val backend = when {
            engine == "Ren'Py" || engine.startsWith("Windows") -> "wine"
            engine == "RPG Maker MV/MZ" -> "rpgmaker-webview"
            else -> "webview"
        }

        // Extract library avatar: PE icon first, then common PNG fallbacks.
        var iconDataUrl = ""
        firstExeUri?.let { exeUri ->
            iconDataUrl = ExeIconExtractor.extractDataUrl(this, exeUri)
            if (iconDataUrl.isNotBlank()) {
                stats.put("exe_uri", exeUri.toString())
            }
        }
        if (iconDataUrl.isBlank() && iconPngUri != null) {
            iconDataUrl = ExeIconExtractor.extractImageDataUrl(this, iconPngUri!!)
        }
        if (firstExeUri != null) {
            stats.put("exe_uri", firstExeUri.toString())
        }

        stats.put("uri", uri.toString())
        stats.put("root", uri.toString())
        stats.put("path", uri.toString())
        stats.put("name", root.name ?: "Selected folder")
        stats.put("title", root.name ?: "Selected folder")
        stats.put("engine", engine)
        stats.put("exe", firstExe)
        stats.put("backend", backend)
        stats.put("iconDataUrl", iconDataUrl)
        stats.put("rpgEntry", rpgEntry)
        stats.put("renpyEntry", renpyEntry)
        stats.put("fileCount", fileCount)
        stats.put("dirCount", dirCount)
        stats.put("mapCount", mapCount)
        stats.put("dataFileCount", dataFileCount)
        stats.put("scriptCount", scriptCount)
        stats.put("actorCount", actorCount)
        stats.put("itemCount", itemCount)
        stats.put("textHintCount", textHintCount)
        stats.put("highlights", highlights)
        stats.put("note", advice)
        stats.put("launchAdvice", advice)
        return stats
    }

    private fun scanSingleExe(uri: Uri): JSONObject {
        val name = displayNameForUri(uri).ifBlank { "Windows EXE" }
        val highlights = JSONArray()
            .put(JSONObject().put("label", "Executable").put("value", name))
            .put(JSONObject().put("label", "Backend").put("value", "Wine + Box64"))
        val advice = "Windows EXE selected. It will launch through RPGTL Wine/Box64."
        val iconDataUrl = ExeIconExtractor.extractDataUrl(this, uri)
        return JSONObject()
            .put("uri", uri.toString())
            .put("root", uri.toString())
            .put("name", name)
            .put("title", name.removeSuffix(".exe").removeSuffix(".EXE"))
            .put("engine", "Windows exe / Wine backend")
            .put("exe", uri.toString())
            .put("exe_uri", uri.toString())
            .put("path", uri.toString())
            .put("backend", "wine")
            .put("iconDataUrl", iconDataUrl)
            .put("fileCount", 1)
            .put("dirCount", 0)
            .put("mapCount", 0)
            .put("dataFileCount", 0)
            .put("scriptCount", 0)
            .put("textHintCount", 0)
            .put("highlights", highlights)
            .put("note", advice)
            .put("launchAdvice", advice)
    }

    private fun findSelectedExeUri(): Uri? {
        lastExeUri?.let { return it }
        val root = lastTreeUri?.let { DocumentFile.fromTreeUri(this, it) } ?: return null
        return findFirstExe(root)?.uri
    }

    private fun displayNameForUri(uri: Uri): String {
        val document = DocumentFile.fromSingleUri(this, uri)
        val fromDocument = document?.name.orEmpty()
        if (fromDocument.isNotBlank()) return fromDocument
        val decoded = runCatching { Uri.decode(uri.lastPathSegment ?: "") }.getOrDefault(uri.lastPathSegment ?: "")
        return decoded.substringAfterLast('/').substringAfterLast(':').ifBlank { uri.toString() }
    }

    private fun isLikelyExeUri(value: String): Boolean {
        val lower = value.lowercase()
        return lower.endsWith(".exe") ||
            lower.contains(".exe?") ||
            lower.contains("%2eexe") ||
            lower.contains("application/x-msdownload")
    }

    private fun findRpgMakerEntry(root: File): File? {
        val wwwEntry = File(root, "www/index.html")
        if (wwwEntry.exists()) return wwwEntry
        val directEntry = File(root, "index.html")
        if (directEntry.exists()) return directEntry
        return root.walkTopDown()
            .firstOrNull { it.isFile && it.name.equals("index.html", ignoreCase = true) }
    }

    private fun findRpgMakerEntry(root: DocumentFile): DocumentFile? {
        val files = root.listFiles()
        files.firstOrNull { it.isDirectory && it.name.equals("www", ignoreCase = true) }?.let { www ->
            www.listFiles().firstOrNull { it.isFile && it.name.equals("index.html", ignoreCase = true) }?.let {
                return it
            }
        }
        files.firstOrNull { it.isFile && it.name.equals("index.html", ignoreCase = true) }?.let {
            return it
        }
        return null
    }

    private fun readDocumentTextProbe(file: DocumentFile, maxBytes: Int = 96 * 1024): String {
        return try {
            contentResolver.openInputStream(file.uri)?.use { input ->
                val bytes = ByteArray(maxBytes)
                val count = input.read(bytes)
                if (count <= 0) "" else String(bytes, 0, count, Charsets.UTF_8)
            }.orEmpty()
        } catch (_: Throwable) {
            ""
        }
    }

    private fun isThirdPartyToolLoader(file: DocumentFile): Boolean {
        val html = readDocumentTextProbe(file).lowercase()
        if (html.isBlank()) return false
        return html.contains("tool is corrupted") ||
            html.contains("the tool is corrupted") ||
            html.contains("you may need to re-download the tool") ||
            (html.contains("mtool") && (html.contains("discord") || html.contains("click to exit") || html.contains("loading")))
    }

    private fun hasRpgMakerRuntimeShape(base: DocumentFile): Boolean {
        val data = base.findFile("data")
        val hasSystem = data?.isDirectory == true && data.findFile("System.json")?.isFile == true
        if (!hasSystem) return false
        val js = base.findFile("js")
        val hasRuntimeJs = js?.isDirectory == true && (
            js.findFile("rpg_core.js")?.isFile == true ||
            js.findFile("rpg_managers.js")?.isFile == true ||
            js.findFile("main.js")?.isFile == true
        )
        return hasRuntimeJs || base.findFile("package.json")?.isFile == true
    }

    private fun isValidRpgMakerEntry(base: DocumentFile, index: DocumentFile): Boolean {
        if (!index.isFile || !index.name.equals("index.html", ignoreCase = true)) return false
        if (isThirdPartyToolLoader(index)) return false
        return hasRpgMakerRuntimeShape(base)
    }

    private fun isValidRpgMakerEntryPath(root: DocumentFile, entryPath: String): Boolean {
        val index = findDocumentByPathNoCache(root, entryPath) ?: return false
        val basePath = entryPath.substringBeforeLast("/", "")
        val base = if (basePath.isBlank()) root else findDocumentByPathNoCache(root, basePath) ?: return false
        return isValidRpgMakerEntry(base, index)
    }

    private fun findRpgMakerEntryPath(root: DocumentFile): String? {
        val files = root.listFiles()
        files.firstOrNull { it.isDirectory && it.name.equals("www", ignoreCase = true) }?.let { www ->
            www.listFiles().firstOrNull { it.isFile && it.name.equals("index.html", ignoreCase = true) }?.let { index ->
                if (isValidRpgMakerEntry(www, index)) return "${www.name ?: "www"}/${index.name ?: "index.html"}"
            }
        }
        files.firstOrNull { it.isFile && it.name.equals("index.html", ignoreCase = true) }?.let { index ->
            if (isValidRpgMakerEntry(root, index)) return index.name ?: "index.html"
        }
        return null
    }

    private fun findRenpyWebEntry(root: DocumentFile): DocumentFile? {
        root.listFiles().forEach { child ->
            if (child.isFile && child.name.equals("index.html", ignoreCase = true)) {
                return child
            }
        }
        root.listFiles().forEach { child ->
            if (child.isDirectory) {
                val found = findRenpyWebEntry(child)
                if (found != null) return found
            }
        }
        return null
    }

    private fun findRenpyWebEntry(root: File): File? {
        val directEntry = File(root, "index.html")
        if (directEntry.exists()) return directEntry
        return root.walkTopDown()
            .firstOrNull { it.isFile && it.name.equals("index.html", ignoreCase = true) }
    }

    private fun findFirstExe(root: DocumentFile): DocumentFile? {
        root.listFiles().forEach { child ->
            if (child.isFile && child.name?.endsWith(".exe", ignoreCase = true) == true) {
                return child
            }
        }
        root.listFiles().forEach { child ->
            if (child.isDirectory) {
                val found = findFirstExe(child)
                if (found != null) return found
            }
        }
        return null
    }

    private fun openExternalExe(exeUri: Uri) {
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(exeUri, "application/x-msdownload")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            startActivity(Intent.createChooser(intent, "Choose exe runner"))
            notifyWeb("Exe was passed to an external compatible runner.")
        } catch (_: ActivityNotFoundException) {
            val fallback = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(exeUri, "application/octet-stream")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            try {
                startActivity(Intent.createChooser(fallback, "Choose exe runner"))
                notifyWeb("Tried opening exe with generic file type.")
            } catch (error: ActivityNotFoundException) {
                notifyWeb("No app can open exe. Install JoiPlay, Winlator, or another compatible runner.")
            }
        }
    }

    private fun escapeJs(value: String): String {
        return value
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "")
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (toolPageGameMode || externalSourceApp == "rpgtl_wine") {
                returnToGame()
                return true
            }
            if (lastGameUrl.isNotBlank()) {
                toggleToolPage()
                return true
            }
            if (!gameViewActive && binding.webView.canGoBack()) {
                binding.webView.goBack()
                return true
            }
        }
        return super.onKeyDown(keyCode, event)
    }
}

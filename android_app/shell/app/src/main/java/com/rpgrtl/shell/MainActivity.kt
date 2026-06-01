package com.rpgrtl.shell

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
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
    private var touchBlockerView: View? = null
    private var touchBlocked = false
    private var externalSourceApp = ""
    private var externalContainerId = -1
    private var externalContainerName = ""
    private var externalGameTitle = ""
    private var externalGamePath = ""
    private var externalTargetPage = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        createStartMs = System.nanoTime()
        setTheme(R.style.Theme_RPGRenPyLocalizer)
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        consumeExternalLaunchIntent(intent)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        enterImmersiveMode()
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
        if (!externalGamePath.isBlank() || externalContainerId >= 0 || externalContainerName.isNotBlank()) {
            notifyWeb("Connected from Winlator: ${externalGameTitle.ifBlank { externalContainerName.ifBlank { "game" } }}")
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) enterImmersiveMode()
    }

    override fun onResume() {
        super.onResume()
        enterImmersiveMode()
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

    private fun enterImmersiveMode() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
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
        val extras = JSONObject().apply {
            put("source_app", externalSourceApp)
            put("container_id", externalContainerId)
            put("container_name", externalContainerName)
            put("game_title", externalGameTitle)
            put("game_path", externalGamePath)
            put("target_page", externalTargetPage)
        }
        getPreferences(Context.MODE_PRIVATE)
            .edit()
            .putString("external_launch_context", extras.toString())
            .apply()
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

    private fun loadToolPage() {
        gameViewActive = false
        updateToolButton()
        clearTouchControls()
        removeGameToolbar()
        setGameTouchBlocked(false)
        binding.gameWebView.visibility = View.INVISIBLE
        binding.webView.visibility = View.VISIBLE
        if (binding.webView.url.isNullOrBlank()) {
            binding.webView.loadUrl("file:///android_asset/mobile_ui/index.html")
        }
        pushExternalLaunchContext()
        reflowWebViewSoon()
        binding.webView.postDelayed({ preloadGameIfReady() }, 3000)
    }

    private fun showGamePage() {
        if (lastGameUrl.isBlank()) {
            loadToolPage()
            return
        }
        gameViewActive = true
        updateToolButton()
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
            loadToolPage()
        } else {
            showGamePage()
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
        toolbar.addView(toolbarButton(if (expanded) "‹" else "⚙", if (expanded) "收起" else "工具") {
            renderGameToolbar(!gameToolbarExpanded)
        })
        if (!expanded) return
        toolbar.addView(toolbarButton("↻", "旋转") { toolbarAction("rotate") })
        toolbar.addView(toolbarButton(if (touchBlocked) "●" else "◌", if (touchBlocked) "恢复触摸" else "禁用触摸", touchBlocked) { toolbarAction("touchToggle") })
        toolbar.addView(toolbarButton("⌨", "键盘") { toolbarAction("keyboard") })
        toolbar.addView(toolbarButton("×", "关闭") { toolbarAction("close") })
        toolbar.postDelayed({
            if (gameToolbarExpanded) renderGameToolbar(false)
        }, 10_000)
    }

    private fun toolbarButton(icon: String, label: String, active: Boolean = false, action: () -> Unit): TextView {
        return TextView(this).apply {
            text = icon
            contentDescription = label
            textSize = if (icon == "⚙") 21f else 18f
            gravity = android.view.Gravity.CENTER
            setTextColor(Color.WHITE)
            background = android.graphics.drawable.GradientDrawable().apply {
                shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                cornerRadii = floatArrayOf(0f, 0f, dp(7f).toFloat(), dp(7f).toFloat(), dp(7f).toFloat(), dp(7f).toFloat(), 0f, 0f)
                setColor(if (active) 0xCCB23A3A.toInt() else 0x99000000.toInt())
                setStroke(dp(1f), 0x55FFFFFF)
            }
            setOnClickListener {
                action()
                if (label != "收起" && label != "工具") {
                    gameToolbarView?.postDelayed({ if (gameToolbarExpanded) renderGameToolbar(false) }, 1500)
                }
            }
            layoutParams = LinearLayout.LayoutParams(dp(42f), dp(42f)).apply {
                bottomMargin = dp(2f)
            }
        }
    }

    private fun toolbarAction(action: String) {
        when (action) {
            "rotate" -> toggleOrientation()
            "touchToggle" -> setGameTouchBlocked(!touchBlocked)
            "keyboard" -> showGameKeyboard()
            "close" -> loadToolPage()
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
        if (lastGameUrl.isBlank()) {
            binding.toolButton.visibility = View.GONE
            return
        }
        binding.toolButton.visibility = View.VISIBLE
        binding.toolButton.text = if (gameViewActive) "Tool" else "Back"
        binding.toolButton.bringToFront()
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
            val uri = Uri.parse(uriText)
            if (isLikelyExeUri(uriText)) {
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
                val sourceEntry = cachedEntryPath.takeIf { it.isNotBlank() && findDocumentByPathNoCache(source, it) != null }
                    ?: findRpgMakerEntryPath(source)
                    ?: throw IllegalStateException("MV/MZ entry not found. Select a folder containing www/index.html or index.html.")
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
                gameViewActive = true
                gamePreloaded = false
                notifyWeb("On-demand mode enabled. Entry: $sourceEntry")
                runOnUiThread {
                    if (sessionId != runSessionId) return@runOnUiThread
                    updateToolButton()
                    applyLaunchSettings()
                    binding.webView.visibility = View.GONE
                    binding.gameWebView.visibility = View.VISIBLE
                    binding.gameWebView.loadUrl(virtualEntry)
                    binding.gameWebView.postDelayed({ if (gameViewActive) applyTouchControls() }, 700)
                }
            } catch (error: Throwable) {
                if (sessionId == runSessionId) notifyWeb("Launch failed: ${error.message}")
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
                dispatchProjectScanned(result)
            } catch (error: Throwable) {
                notifyWeb("Scan failed: ${error.message}")
            }
        }.start()
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
                        gameViewActive = true
                        updateToolButton()
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
                        openExternalExe(exe.uri)
                    }
                    return@Thread
                }
                notifyWeb("RenPy resources found, but no Android/Web entry was found. Use a compatible runner for Windows exe games.")
            } catch (error: Throwable) {
                if (sessionId == runSessionId) notifyWeb("RenPy launch failed: ${error.message}")
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
                    openExternalExe(exe.uri)
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
            if (!request.has("settings")) {
                val saved = getPreferences(Context.MODE_PRIVATE)
                    .getString("android_ai_settings_json", "") ?: ""
                if (saved.isNotBlank()) request.put("settings", JSONObject(saved))
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

    fun saveLaunchSettings(json: String) {
        getPreferences(Context.MODE_PRIVATE)
            .edit()
            .putString("launch_settings_json", json)
            .apply()
        applyLaunchSettings()
        if (gameViewActive && lastGameUrl.isNotBlank()) {
            binding.gameWebView.reload()
        }
        notifyWeb("Launch settings saved.")
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
            }
            target.setLayerType(if (webgl) View.LAYER_TYPE_HARDWARE else View.LAYER_TYPE_SOFTWARE, null)
        }
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
        binding.webView.evaluateJavascript(
            "window.onAndroidGameFolderPicked && window.onAndroidGameFolderPicked('$escaped')",
            null
        )
        scanSelectedGame()
    }

    private fun dispatchExePicked(uri: Uri) {
        val escaped = escapeJs(uri.toString())
        binding.webView.evaluateJavascript(
            "window.onAndroidGameExePicked && window.onAndroidGameExePicked('$escaped')",
            null
        )
        dispatchProjectScanned(scanSingleExe(uri))
    }

    fun dispatchRestoredFolderIfAny() {
        val uri = lastTreeUri ?: return
        dispatchFolderPicked(uri)
    }

    private fun dispatchProjectScanned(payload: JSONObject) {
        val escaped = escapeJs(payload.toString())
        runOnUiThread {
            binding.webView.evaluateJavascript(
                "window.onAndroidProjectScanned && window.onAndroidProjectScanned('$escaped')",
                null
            )
        }
    }

    private fun notifyWeb(message: String) {
        val escaped = escapeJs(message)
        runOnUiThread {
            binding.webView.evaluateJavascript(
                "window.onAndroidShellMessage && window.onAndroidShellMessage('$escaped')",
                null
            )
        }
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
            val view = TextView(this).apply {
                text = if (isJoystick) "O" else item.optString("label", "A")
                textSize = if (isJoystick) 18f else 15f
                gravity = android.view.Gravity.CENTER
                setTextColor(0xEEFFFFFF.toInt())
                alpha = item.optDouble("opacity", 0.62).coerceIn(0.18, 1.0).toFloat()
                background = android.graphics.drawable.GradientDrawable().apply {
                    shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                    cornerRadius = if (isJoystick) size / 2f else dp(7f).toFloat()
                    setColor(if (isJoystick) 0x553C9DFF else 0xAA101820.toInt())
                    setStroke(dp(1f), 0xAA3DE0D0.toInt())
                }
            }
            val left = (rootWidth * x - size / 2.0).toInt().coerceIn(0, (rootWidth - size).coerceAtLeast(0))
            val top = (rootHeight * y - size / 2.0).toInt().coerceIn(0, (rootHeight - size).coerceAtLeast(0))
            val params = FrameLayout.LayoutParams(size, size).apply {
                leftMargin = left
                topMargin = top
            }
            if (isJoystick) {
                var activeDir: Int? = null
                fun release() {
                    activeDir?.let { dispatchKeyToGame(it, KeyEvent.ACTION_UP) }
                    activeDir = null
                }
                fun press(code: Int) {
                    if (activeDir == code) return
                    release()
                    activeDir = code
                    dispatchKeyToGame(code, KeyEvent.ACTION_DOWN)
                }
                view.setOnTouchListener { _, event ->
                    when (event.actionMasked) {
                        android.view.MotionEvent.ACTION_DOWN,
                        android.view.MotionEvent.ACTION_MOVE -> {
                            val dx = event.x - size / 2f
                            val dy = event.y - size / 2f
                            if (kotlin.math.abs(dx) < dp(8f) && kotlin.math.abs(dy) < dp(8f)) {
                                release()
                            } else if (kotlin.math.abs(dx) > kotlin.math.abs(dy)) {
                                press(if (dx > 0) KeyEvent.KEYCODE_DPAD_RIGHT else KeyEvent.KEYCODE_DPAD_LEFT)
                            } else {
                                press(if (dy > 0) KeyEvent.KEYCODE_DPAD_DOWN else KeyEvent.KEYCODE_DPAD_UP)
                            }
                            true
                        }
                        android.view.MotionEvent.ACTION_UP,
                        android.view.MotionEvent.ACTION_CANCEL -> {
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
                            dispatchKeyToGame(keyCode, KeyEvent.ACTION_DOWN)
                            true
                        }
                        android.view.MotionEvent.ACTION_UP,
                        android.view.MotionEvent.ACTION_CANCEL -> {
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
        enterImmersiveMode()
        val target = if (gameViewActive) binding.gameWebView else binding.webView
        target.postDelayed({
            target.evaluateJavascript(
                """
                (function(){
                  if(document.body && document.body.style){
                    document.body.style.display = '';
                    document.body.style.zoom = '1';
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
            KeyEvent.KEYCODE_BACK -> "Escape"
            KeyEvent.KEYCODE_SHIFT_LEFT, KeyEvent.KEYCODE_SHIFT_RIGHT -> "Shift"
            KeyEvent.KEYCODE_CTRL_LEFT, KeyEvent.KEYCODE_CTRL_RIGHT -> "Control"
            KeyEvent.KEYCODE_ESCAPE -> "Escape"
            KeyEvent.KEYCODE_SPACE -> " "
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
            KeyEvent.KEYCODE_BACK -> "Escape"
            KeyEvent.KEYCODE_SHIFT_LEFT, KeyEvent.KEYCODE_SHIFT_RIGHT -> "ShiftLeft"
            KeyEvent.KEYCODE_CTRL_LEFT, KeyEvent.KEYCODE_CTRL_RIGHT -> "ControlLeft"
            KeyEvent.KEYCODE_ESCAPE -> "Escape"
            KeyEvent.KEYCODE_SPACE -> "Space"
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
            else -> 13
        }
    }

    fun openGameAsset(relativePath: String): WebResourceResponse? {
        val root = gameTreeRoot ?: return null
        val normalized = normalizeGamePath(relativePath)
        val file = findGameDocument(root, normalized) ?: return null
        if (!file.isFile) return null
        translatedGameAsset(normalized)?.let { return it }
        val stream = contentResolver.openInputStream(file.uri) ?: return null
        return WebResourceResponse(
            mimeTypeForPath(normalized),
            "UTF-8",
            200,
            "OK",
            cacheHeadersForPath(normalized),
            stream
        )
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
            val index = mutableMapOf<String, DocumentFile>()
            val pathIndex = mutableMapOf<String, String>()
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
                gameFileIndex = emptyMap()
            }
        }.start()
    }

    fun androidLaunchGame(backend: String): String {
        val normalized = backend.lowercase()
        if (normalized.contains("wine")) {
            val targetExe = lastExeUri ?: findSelectedExeUri()
            val title = externalGameTitle.ifBlank { targetExe?.let { displayNameForUri(it) }.orEmpty() }
            return WineEngineBridge(this).launch(targetExe, title).toString()
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

        fun walk(node: DocumentFile, relative: String, depth: Int) {
            if (depth > 3 || fileCount > 420) return
            val children = node.listFiles()
            children.forEach { child ->
                if ((rpgEntry.isNotBlank() && hasRpgData) || (renpyEntry.isNotBlank() && hasRenpyGame)) return@forEach
                val name = child.name ?: return@forEach
                val path = if (relative.isBlank()) name else "$relative/$name"
                if (child.isDirectory) {
                    dirCount += 1
                    if (name.equals("www", ignoreCase = true)) {
                        addHighlight("RPG Maker folder", path)
                        val data = child.findFile("data")
                        inspectDataDir(data, "$path/data")
                        child.findFile("index.html")?.let {
                            rpgEntry = if (rpgEntry.isBlank()) "$path/index.html" else rpgEntry
                            addHighlight("MV/MZ Web entry", "$path/index.html")
                        }
                    }
                    if (name.equals("data", ignoreCase = true) && child.findFile("System.json") != null) {
                        inspectDataDir(child, path)
                    }
                    if (name.equals("game", ignoreCase = true)) {
                        hasRenpyGame = true
                        addHighlight("RenPy game folder", path)
                    }
                    walk(child, path, depth + 1)
                } else if (child.isFile) {
                    fileCount += 1
                    val lower = name.lowercase()
                    if (firstExe.isBlank() && lower.endsWith(".exe")) {
                        firstExe = path
                        addHighlight("Executable", path)
                    }
                    if (rpgEntry.isBlank() && lower == "index.html" && (relative.equals("www", true) || path.equals("index.html", true))) {
                        rpgEntry = path
                        addHighlight("MV/MZ Web entry", path)
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

        stats.put("uri", uri.toString())
        stats.put("name", root.name ?: "Selected folder")
        stats.put("engine", engine)
        stats.put("exe", firstExe)
        stats.put("backend", if (engine == "Windows exe / compatible runner") "wine" else "webview")
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
        if (rpgEntry.isNotBlank() && hasRpgData) {
            gameTreeRoot = root
            gameVirtualBase = rpgEntry.substringBeforeLast("/", "")
            cachedEntryPath = rpgEntry
            lastGameUrl = "https://rpgrtl.local/game/$rpgEntry"
            gamePreloaded = false
            updateToolButton()
            getPreferences(Context.MODE_PRIVATE)
                .edit()
                .putString("last_rpg_entry_path", rpgEntry)
                .apply()
            restoreGamePathIndex(uri)
            buildGameFileIndex(root, uri)
        }
        return stats
    }

    private fun scanSingleExe(uri: Uri): JSONObject {
        val name = displayNameForUri(uri).ifBlank { "Windows EXE" }
        val highlights = JSONArray()
            .put(JSONObject().put("label", "Executable").put("value", name))
            .put(JSONObject().put("label", "Backend").put("value", "Wine + Box64"))
        val advice = "Windows EXE selected. It will launch through RPGTL Wine/Box64."
        return JSONObject()
            .put("uri", uri.toString())
            .put("root", uri.toString())
            .put("name", name)
            .put("engine", "Windows exe / Wine backend")
            .put("exe", uri.toString())
            .put("backend", "wine")
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

    private fun findRpgMakerEntryPath(root: DocumentFile): String? {
        val files = root.listFiles()
        files.firstOrNull { it.isDirectory && it.name.equals("www", ignoreCase = true) }?.let { www ->
            www.listFiles().firstOrNull { it.isFile && it.name.equals("index.html", ignoreCase = true) }?.let {
                return "${www.name ?: "www"}/${it.name ?: "index.html"}"
            }
        }
        files.firstOrNull { it.isFile && it.name.equals("index.html", ignoreCase = true) }?.let {
            return it.name ?: "index.html"
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

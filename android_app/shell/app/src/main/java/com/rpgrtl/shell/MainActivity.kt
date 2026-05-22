package com.rpgrtl.shell

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.webkit.WebSettings
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.widget.FrameLayout
import android.widget.TextView
import androidx.documentfile.provider.DocumentFile
import com.rpgrtl.shell.databinding.ActivityMainBinding
import java.io.File
import java.io.InputStream
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : Activity() {
    private lateinit var binding: ActivityMainBinding
    private val pickGameFolderRequest = 7101
    private var lastTreeUri: Uri? = null
    private var gameTreeRoot: DocumentFile? = null
    private var gameVirtualBase = ""
    private val gameAssetCache = mutableMapOf<String, DocumentFile?>()
    private val gameDirectoryCache = mutableMapOf<String, List<DocumentFile>>()
    @Volatile private var runSessionId = 0
    private val touchButtonViews = mutableListOf<View>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        enterImmersiveMode()
        setupWebView(binding.webView)
        binding.toolButton.setOnClickListener {
            binding.toolButton.visibility = android.view.View.GONE
            clearTouchControls()
            loadToolPage()
        }
        restoreLastTreeUri()
        loadToolPage()
        requestStartupPermissions()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) enterImmersiveMode()
    }

    override fun onResume() {
        super.onResume()
        enterImmersiveMode()
        binding.webView.onResume()
    }

    override fun onPause() {
        binding.webView.onPause()
        super.onPause()
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

    private fun setupWebView(webView: WebView) {
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
            setSupportMultipleWindows(false)
            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false
        }
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null)
        webView.webViewClient = ShellWebViewClient(this)
        webView.addJavascriptInterface(ShellBridge(this), "RPGRenPyShell")
        webView.isFocusable = true
        webView.isFocusableInTouchMode = true
        webView.requestFocus()
    }

    private fun loadToolPage() {
        binding.toolButton.visibility = android.view.View.GONE
        clearTouchControls()
        binding.webView.loadUrl("file:///android_asset/mobile_ui/index.html")
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

    fun launchSelectedGame() {
        val uri = lastTreeUri
        if (uri == null) {
            notifyWeb("请先选择游戏目录。")
            return
        }
        Thread {
            val sessionId = nextRunSession()
            try {
                notifyWeb("正在检查 RPG Maker MV/MZ 入口...")
                val source = DocumentFile.fromTreeUri(this, uri)
                    ?: throw IllegalStateException("无法读取所选目录。")
                val sourceEntry = findRpgMakerEntryPath(source)
                    ?: throw IllegalStateException("未找到 MV/MZ 入口。请选择包含 www/index.html 或 index.html 的游戏目录。")
                gameTreeRoot = source
                gameVirtualBase = sourceEntry.substringBeforeLast("/", "")
                val virtualEntry = "https://rpgrtl.local/game/$sourceEntry"
                notifyWeb("已启用按需读取模式，不复制整个游戏目录。\n入口：$sourceEntry")
                runOnUiThread {
                    if (sessionId != runSessionId) return@runOnUiThread
                    binding.toolButton.visibility = android.view.View.VISIBLE
                    applyLaunchSettings()
                    applyTouchControls()
                    binding.webView.loadUrl(virtualEntry)
                }
            } catch (error: Throwable) {
                if (sessionId == runSessionId) notifyWeb("启动失败：${error.message}")
            }
        }.start()
    }

    fun scanSelectedGame() {
        val uri = lastTreeUri
        if (uri == null) {
            notifyWeb("请先选择游戏目录。")
            return
        }
        Thread {
            try {
                notifyWeb("正在扫描目录和子目录...")
                val source = DocumentFile.fromTreeUri(this, uri)
                    ?: throw IllegalStateException("无法读取所选目录。")
                val result = scanGameTree(source, uri)
                dispatchProjectScanned(result)
            } catch (error: Throwable) {
                notifyWeb("扫描失败：${error.message}")
            }
        }.start()
    }

    fun launchRenpyGame() {
        val uri = lastTreeUri
        if (uri == null) {
            notifyWeb("请先选择游戏目录。")
            return
        }
        Thread {
            val sessionId = nextRunSession()
            try {
                notifyWeb("正在识别 Ren'Py Android/Web 运行入口...")
                val source = DocumentFile.fromTreeUri(this, uri)
                    ?: throw IllegalStateException("无法读取所选目录。")
                if (findRenpyWebEntry(source) != null) {
                    notifyWeb("检测到 Ren'Py Web 入口，正在复制运行资源...")
                    val localRoot = File(cacheDir, "rpgrtl_renpy_runtime").apply {
                        deleteRecursively()
                        mkdirs()
                    }
                    copyDocumentTree(source, localRoot)
                    val localEntry = findRenpyWebEntry(localRoot)
                        ?: throw IllegalStateException("复制后未找到 Ren'Py Web index.html。")
                    runOnUiThread {
                        if (sessionId != runSessionId) return@runOnUiThread
                        binding.toolButton.visibility = android.view.View.VISIBLE
                        applyTouchControls()
                        binding.webView.loadUrl(localEntry.toURI().toString())
                    }
                    notifyWeb("已用 WebView 打开 Ren'Py Web 入口。")
                    return@Thread
                }
                val exe = findFirstExe(source)
                if (exe != null) {
                    runOnUiThread {
                        openExternalExe(exe.uri)
                    }
                    return@Thread
                }
                notifyWeb("已识别为 Ren'Py 目录，但没有找到 Android/Web 可直接运行入口。Windows 版 Ren'Py 需要用 Ren'Py Launcher/RAPT 重新打包成 APK，或安装兼容运行器后从 exe 打开。")
            } catch (error: Throwable) {
                if (sessionId == runSessionId) notifyWeb("Ren'Py 启动失败：${error.message}")
            }
        }.start()
    }

    fun launchExeWithExternalRunner() {
        val uri = lastTreeUri
        if (uri == null) {
            notifyWeb("请先选择游戏目录。")
            return
        }
        Thread {
            val sessionId = nextRunSession()
            try {
                notifyWeb("正在查找 exe 文件...")
                val source = DocumentFile.fromTreeUri(this, uri)
                    ?: throw IllegalStateException("无法读取所选目录。")
                val exe = findFirstExe(source)
                    ?: throw IllegalStateException("所选目录里没有找到 exe 文件。")
                runOnUiThread {
                    if (sessionId != runSessionId) return@runOnUiThread
                    openExternalExe(exe.uri)
                }
            } catch (error: Throwable) {
                if (sessionId == runSessionId) notifyWeb("打开 exe 失败：${error.message}")
            }
        }.start()
    }

    fun androidTranslationEntries(limit: Int): String {
        return androidRpgServiceResult { service ->
            service.translationEntries(limit)
        }
    }

    fun androidDataRecords(category: String, limit: Int): String {
        return androidRpgServiceResult { service ->
            service.dataRecords(category, limit)
        }
    }

    fun androidUpdateRecord(recordJson: String, newValue: String): String {
        return androidRpgServiceResult { service ->
            service.updateRecord(recordJson, newValue)
        }
    }

    fun androidMaps(): String {
        return androidRpgServiceResult { service ->
            service.maps()
        }
    }

    fun androidMapDetail(mapId: Int): String {
        return androidRpgServiceResult { service ->
            service.mapDetail(mapId)
        }
    }

    fun androidSaveSlots(): String {
        return androidRpgServiceResult { service ->
            service.saveSlots()
        }
    }

    fun androidCreateSaveBackup(): String {
        return androidRpgServiceResult { service ->
            service.createSaveBackup()
        }
    }

    fun androidBackups(): String {
        return androidRpgServiceResult { service ->
            service.backups()
        }
    }

    private fun androidRpgServiceResult(block: (AndroidRpgMakerService) -> JSONObject): String {
        return try {
            val uri = lastTreeUri ?: throw IllegalStateException("请先选择游戏目录。")
            val source = DocumentFile.fromTreeUri(this, uri)
                ?: throw IllegalStateException("无法读取所选目录。")
            block(AndroidRpgMakerService(this, source)).toString()
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
        notifyWeb("触屏按键布局已保存。启动游戏后会自动覆盖到游戏画面上。")
    }

    fun saveLaunchSettings(json: String) {
        getPreferences(Context.MODE_PRIVATE)
            .edit()
            .putString("launch_settings_json", json)
            .apply()
        applyLaunchSettings()
        notifyWeb("启动设置已保存。下一次启动 HTML / RPG Maker 游戏时会自动应用。")
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
        with(binding.webView.settings) {
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
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        }
        binding.webView.setLayerType(
            if (webgl) View.LAYER_TYPE_HARDWARE else View.LAYER_TYPE_SOFTWARE,
            null
        )
    }

    @Deprecated("Deprecated in Android API but fine for this minimal shell prototype.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != pickGameFolderRequest || resultCode != RESULT_OK) return
        val uri = data?.data ?: return
        val flags = data.flags and (
            Intent.FLAG_GRANT_READ_URI_PERMISSION or
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )
        contentResolver.takePersistableUriPermission(uri, flags)
        lastTreeUri = uri
        getPreferences(Context.MODE_PRIVATE)
            .edit()
            .putString("last_game_tree_uri", uri.toString())
            .apply()
        dispatchFolderPicked(uri)
    }

    private fun restoreLastTreeUri() {
        val raw = getPreferences(Context.MODE_PRIVATE).getString("last_game_tree_uri", "") ?: ""
        if (raw.isNotBlank()) {
            lastTreeUri = Uri.parse(raw)
        }
    }

    private fun dispatchFolderPicked(uri: Uri) {
        val escaped = escapeJs(uri.toString())
        binding.webView.evaluateJavascript(
            "window.onAndroidGameFolderPicked && window.onAndroidGameFolderPicked('$escaped')",
            null
        )
        scanSelectedGame()
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

    private fun nextRunSession(): Int {
        runSessionId += 1
        return runSessionId
    }

    private fun applyTouchControls() {
        clearTouchControls()
        val raw = getPreferences(Context.MODE_PRIVATE).getString("touch_controls_json", "") ?: defaultTouchControlsJson()
        try {
            val root = JSONObject(raw)
            val enabled = root.optBoolean("enabled", true)
            if (!enabled) return
            val buttons = root.optJSONArray("buttons") ?: JSONArray()
            for (index in 0 until buttons.length()) {
                val item = buttons.optJSONObject(index) ?: continue
                addTouchButton(item)
            }
            binding.toolButton.bringToFront()
            touchButtonViews.forEach { it.bringToFront() }
            touchButtonViews.forEach { it.elevation = 24f }
            binding.toolButton.elevation = 32f
        } catch (error: Throwable) {
            notifyWeb("触屏布局读取失败：${error.message}")
        }
    }

    private fun defaultTouchControlsJson(): String {
        return """
            {
              "enabled": true,
              "buttons": [
                {"id":"up","label":"↑","keyCode":19,"x":0.18,"y":0.58,"size":58,"opacity":0.62,"enabled":true},
                {"id":"down","label":"↓","keyCode":20,"x":0.18,"y":0.78,"size":58,"opacity":0.62,"enabled":true},
                {"id":"left","label":"←","keyCode":21,"x":0.09,"y":0.68,"size":58,"opacity":0.62,"enabled":true},
                {"id":"right","label":"→","keyCode":22,"x":0.27,"y":0.68,"size":58,"opacity":0.62,"enabled":true},
                {"id":"ok","label":"A","keyCode":66,"x":0.84,"y":0.66,"size":68,"opacity":0.70,"enabled":true},
                {"id":"cancel","label":"B","keyCode":4,"x":0.72,"y":0.76,"size":62,"opacity":0.58,"enabled":true},
                {"id":"dash","label":"跑","keyCode":59,"x":0.87,"y":0.42,"size":54,"opacity":0.48,"enabled":true},
                {"id":"fast","label":"快","keyCode":113,"x":0.74,"y":0.42,"size":54,"opacity":0.48,"enabled":true}
              ]
            }
        """.trimIndent()
    }

    private fun addTouchButton(item: JSONObject) {
        val enabled = item.optBoolean("enabled", true)
        if (!enabled) return
        val label = item.optString("label", "BTN")
        val keyCode = item.optInt("keyCode", KeyEvent.KEYCODE_ENTER)
        val xRatio = item.optDouble("x", 0.5).coerceIn(0.0, 1.0)
        val yRatio = item.optDouble("y", 0.5).coerceIn(0.0, 1.0)
        val sizeDp = item.optInt("size", 56).coerceIn(28, 160)
        val opacity = item.optDouble("opacity", 0.62).coerceIn(0.12, 1.0).toFloat()
        val view = TextView(this).apply {
            text = label
            textSize = 13f
            gravity = Gravity.CENTER
            setTextColor(android.graphics.Color.WHITE)
            setBackgroundColor(android.graphics.Color.argb((opacity * 255).toInt(), 23, 35, 30))
            setOnTouchListener { _, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        dispatchKeyToGame(keyCode, KeyEvent.ACTION_DOWN)
                        true
                    }
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                        dispatchKeyToGame(keyCode, KeyEvent.ACTION_UP)
                        true
                    }
                    else -> true
                }
            }
        }
        val sizePx = (sizeDp * resources.displayMetrics.density).toInt()
        val params = FrameLayout.LayoutParams(sizePx, sizePx).apply {
            leftMargin = ((resources.displayMetrics.widthPixels - sizePx) * xRatio).toInt()
            topMargin = ((resources.displayMetrics.heightPixels - sizePx) * yRatio).toInt()
        }
        binding.root.addView(view, params)
        view.bringToFront()
        view.elevation = 24f
        touchButtonViews.add(view)
    }

    fun reapplyGameOverlay() {
        runOnUiThread {
            if (binding.toolButton.visibility == View.VISIBLE) {
                applyTouchControls()
            }
        }
    }

    private fun clearTouchControls() {
        touchButtonViews.forEach { view ->
            binding.root.removeView(view)
        }
        touchButtonViews.clear()
    }

    private fun dispatchKeyToGame(keyCode: Int, action: Int) {
        val event = KeyEvent(System.currentTimeMillis(), System.currentTimeMillis(), action, keyCode, 0)
        binding.webView.requestFocus()
        binding.webView.dispatchKeyEvent(event)
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
        binding.webView.evaluateJavascript(script, null)
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
        val stream = contentResolver.openInputStream(file.uri) ?: return null
        return WebResourceResponse(
            mimeTypeForPath(normalized),
            "UTF-8",
            stream
        )
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
                                notifyWeb("正在复制 $label：${copiedFiles.get()}/${stats.files} 个文件，${formatBytes(copiedBytes.get())}/${formatBytes(stats.bytes)}")
                            }
                        }
                    }
                }
                copiedFiles.incrementAndGet()
            }
        }
        if (!target.exists()) target.mkdirs()
        source.listFiles().forEach { copyNode(it, target) }
        notifyWeb("$label 资源复制完成：${copiedFiles.get()} 个文件，${formatBytes(copiedBytes.get())}")
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

        fun walk(node: DocumentFile, relative: String, depth: Int) {
            if (depth > 8 || fileCount > 8000) return
            node.listFiles().forEach { child ->
                val name = child.name ?: return@forEach
                val path = if (relative.isBlank()) name else "$relative/$name"
                if (child.isDirectory) {
                    dirCount += 1
                    if (name.equals("www", ignoreCase = true)) addHighlight("RPG Maker 目录", path)
                    if (name.equals("game", ignoreCase = true)) {
                        hasRenpyGame = true
                        addHighlight("Ren'Py game 目录", path)
                    }
                    walk(child, path, depth + 1)
                } else if (child.isFile) {
                    fileCount += 1
                    val lower = name.lowercase()
                    if (firstExe.isBlank() && lower.endsWith(".exe")) {
                        firstExe = path
                        addHighlight("可执行文件", path)
                    }
                    if (rpgEntry.isBlank() && lower == "index.html" && (relative.equals("www", true) || path.equals("index.html", true))) {
                        rpgEntry = path
                        addHighlight("MV/MZ Web 入口", path)
                    }
                    if (renpyEntry.isBlank() && lower == "index.html" && !relative.equals("www", true)) {
                        renpyEntry = path
                    }
                    if (relative.replace("\\", "/").lowercase().contains("www/data") && lower.endsWith(".json")) {
                        dataFileCount += 1
                        hasRpgData = true
                        if (lower.startsWith("map") && lower != "mapinfos.json") mapCount += 1
                        if (lower == "actors.json") actorCount = 1
                        if (lower == "items.json") itemCount = 1
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
            firstExe.isNotBlank() -> "Windows exe / 兼容运行器"
            else -> "未知"
        }
        val advice = when (engine) {
            "RPG Maker MV/MZ" -> "可以点击“启动手机游戏”。当前使用按需读取模式，不会预先复制整个游戏目录。"
            "Ren'Py" -> if (renpyEntry.isNotBlank()) "可以尝试“启动 Ren'Py”。普通 Windows 版 Ren'Py 仍需要外部运行器或重新打包 APK。" else "检测到 Ren'Py 资源，但没有 Web 入口；Windows 版需要外部运行器或官方 Android 打包。"
            "Windows exe / 兼容运行器" -> "Android 不能原生运行 exe，请点击“外部运行 exe”并选择 JoiPlay、Winlator 等兼容运行器。"
            else -> "没有识别到可直接运行的游戏入口。请确认选择的是游戏根目录。"
        }

        stats.put("uri", uri.toString())
        stats.put("name", root.name ?: "选中目录")
        stats.put("engine", engine)
        stats.put("exe", firstExe)
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
            startActivity(Intent.createChooser(intent, "选择 exe 兼容运行器"))
            notifyWeb("已把 exe 交给外部兼容运行器。若没有可选应用，请安装 JoiPlay、Winlator 或 MTool Android。")
        } catch (_: ActivityNotFoundException) {
            val fallback = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(exeUri, "application/octet-stream")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            try {
                startActivity(Intent.createChooser(fallback, "选择 exe 兼容运行器"))
                notifyWeb("已尝试用通用文件类型打开 exe。")
            } catch (error: ActivityNotFoundException) {
                notifyWeb("没有找到可打开 exe 的应用。请安装 JoiPlay、Winlator 或 MTool Android。")
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
            if (binding.toolButton.visibility == android.view.View.VISIBLE) {
                loadToolPage()
                return true
            }
            if (binding.webView.canGoBack()) {
                binding.webView.goBack()
                return true
            }
        }
        return super.onKeyDown(keyCode, event)
    }
}

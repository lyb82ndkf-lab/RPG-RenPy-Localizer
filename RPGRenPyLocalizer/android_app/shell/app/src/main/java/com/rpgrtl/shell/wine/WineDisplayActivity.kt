package com.rpgrtl.shell.wine

import android.app.AlertDialog
import android.os.Bundle
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.net.Uri
import android.util.Log
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.Toast
import com.rpgrtl.engine.XServerDisplayActivity
import com.rpgrtl.engine.box64.Box64Preset
import com.rpgrtl.engine.container.Container
import com.rpgrtl.engine.container.ContainerManager
import com.rpgrtl.engine.container.GraphicsDrivers
import com.rpgrtl.engine.core.AppUtils
import com.rpgrtl.engine.core.EnvVars
import com.rpgrtl.engine.core.GPUHelper
import com.rpgrtl.engine.core.WineUtils
import com.rpgrtl.engine.widget.InputControlsView
import com.rpgrtl.engine.widget.TouchpadView
import com.rpgrtl.engine.widget.XServerView
import com.rpgrtl.engine.winhandler.WinHandler
import com.rpgrtl.engine.xconnector.UnixSocketConfig
import com.rpgrtl.engine.xenvironment.RootFS
import com.rpgrtl.engine.xenvironment.XEnvironment
import com.rpgrtl.engine.xenvironment.components.GuestProgramLauncherComponent
import com.rpgrtl.engine.xenvironment.components.SysVSharedMemoryComponent
import com.rpgrtl.engine.xenvironment.components.XServerComponent
import com.rpgrtl.engine.xserver.ScreenInfo
import com.rpgrtl.engine.xserver.XServer
import com.rpgrtl.shell.MainActivity
import java.io.File
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap

class WineDisplayActivity : XServerDisplayActivity(), FloatingToolbar.Listener {
    private var launcherComponent: GuestProgramLauncherComponent? = null
    private lateinit var runtimeBridge: RuntimeBridge
    private var toolbar: FloatingToolbar? = null
    private var touchBlocker: View? = null
    private var touchBlocked = false
    private var gameExePath = ""
    private var selectedBox64Preset = Box64Preset.PERFORMANCE
    private var selectedGraphicsDriver = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AppUtils.hideSystemUI(this)
        AppUtils.keepScreenOn(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        gameExePath = intent.getStringExtra(EXTRA_GAME_URI).orEmpty()
        val gameTitle = intent.getStringExtra(EXTRA_GAME_TITLE).orEmpty().ifBlank { "Windows Game" }
        val containerId = intent.getIntExtra(EXTRA_CONTAINER_ID, 0)
        runtimeBridge = RuntimeBridge(containerId.toString())

        if (gameExePath.isBlank()) {
            Toast.makeText(this, "未找到可启动的 exe 路径。", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        rootFS = RootFS.find(this)
        if (!rootFS.isValid) {
            Toast.makeText(this, "Wine RootFS 尚未安装，暂时无法启动 Windows 游戏。", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        if (!prepareContainer(containerId, gameTitle)) return
        gameExePath = prepareExecutablePath(gameExePath, gameTitle)

        screenInfo = ScreenInfo(container.screenSize)
        xServer = XServer(this, screenInfo)
        winHandler = WinHandler(this)
        xServer.setWinHandler(winHandler)

        xServerView = XServerView(this, xServer)
        xServer.setRenderer(xServerView.renderer)

        touchpadView = TouchpadView(this, xServer, false)
        inputControlsView = InputControlsView(this).apply {
            setXServer(xServer)
            setTouchpadView(touchpadView)
            setShowTouchscreenControls(false)
        }

        environment = XEnvironment(this, rootFS)
        addRuntimeComponents()
        setContentView(createDisplayLayout(gameTitle))

        winHandler.start()
        environment.startEnvironmentComponents()
        activeRuntimeBridges[container.id] = runtimeBridge
        Handler(Looper.getMainLooper()).postDelayed({ launcherComponent?.start() }, 1200)

        Toast.makeText(this, "正在通过 Wine + Box64 启动：$gameTitle", Toast.LENGTH_LONG).show()
    }

    private fun prepareContainer(containerId: Int, gameTitle: String): Boolean {
        val manager = ContainerManager(this)
        container = if (containerId > 0) {
            manager.getContainerById(containerId)
        } else {
            manager.containers.firstOrNull()
        }

        if (container == null) {
            Toast.makeText(this, "没有可用 Wine 容器，请先完成 Winlator 运行环境初始化。", Toast.LENGTH_LONG).show()
            finish()
            return false
        }

        if (container.name.isBlank() || container.name.startsWith("Container-")) {
            container.name = gameTitle
        }
        selectedBox64Preset = resolveBox64Preset()
        selectedGraphicsDriver = resolveGraphicsDriver()
        container.box64Preset = selectedBox64Preset
        container.setGraphicsDriver(selectedGraphicsDriver)
        Log.i(TAG, "Wine launch profile: box64=$selectedBox64Preset graphics=$selectedGraphicsDriver")
        manager.activateContainer(container)
        WineUtils.createDosdevicesSymlinks(container, false)
        return true
    }

    private fun addRuntimeComponents() {
        val rootDir = rootFS.rootDir
        environment.addComponent(
            XServerComponent(
                xServer,
                UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.XSERVER_PATH)
            )
        )
        environment.addComponent(
            SysVSharedMemoryComponent(
                xServer,
                UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.SYSVSHM_SERVER_PATH)
            )
        )

        val env = EnvVars(container.envVars)
        env.put("WINEPREFIX", rootDir.absolutePath + RootFS.WINEPREFIX)
        env.put("WINEDLLOVERRIDES", "winemenubuilder.exe=d")
        env.put("NWJS_ARGS", "--remote-debugging-port=${RuntimeBridge.CDP_PORT}")
        env.put("CHROME_REMOTE_DEBUGGING_PORT", RuntimeBridge.CDP_PORT.toString())
        applyPerformanceEnv(env, selectedGraphicsDriver)

        launcherComponent = GuestProgramLauncherComponent().apply {
            setEnvVars(env)
            setBox64Preset(selectedBox64Preset)
            setGuestExecutable(buildGuestCommand(gameExePath))
            setTerminationCallback {
                runOnUiThread {
                    Toast.makeText(this@WineDisplayActivity, "游戏进程已结束。", Toast.LENGTH_SHORT).show()
                }
            }
        }
        environment.addComponent(launcherComponent)
    }

    private fun resolveBox64Preset(): String {
        val requested = intent.getStringExtra(EXTRA_BOX64_PRESET).orEmpty()
            .trim()
            .uppercase(Locale.ENGLISH)
        return when (requested) {
            Box64Preset.STABILITY,
            Box64Preset.CONSERVATIVE,
            Box64Preset.INTERMEDIATE,
            Box64Preset.PERFORMANCE,
            Box64Preset.CUSTOM -> requested
            else -> Box64Preset.PERFORMANCE
        }
    }

    private fun resolveGraphicsDriver(): String {
        val requested = intent.getStringExtra(EXTRA_GRAPHICS_DRIVER).orEmpty()
            .trim()
            .lowercase(Locale.ENGLISH)
        if (requested.isNotBlank() && requested != "auto") {
            return normalizeGraphicsDriver(requested)
        }
        return detectBestGraphicsDriver()
    }

    private fun normalizeGraphicsDriver(value: String): String {
        val parts = GraphicsDrivers.parseIdentifiers(value)
        return "${parts[0]},${parts[1]}"
    }

    private fun detectBestGraphicsDriver(): String {
        val renderer = runCatching { GPUHelper.glGetRenderer(this) }.getOrDefault("")
        val hardware = buildString {
            append(renderer).append(' ')
            append(Build.HARDWARE).append(' ')
            append(Build.BOARD).append(' ')
            append(Build.MANUFACTURER).append(' ')
            append(Build.MODEL).append(' ')
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                append(Build.SOC_MANUFACTURER).append(' ')
                append(Build.SOC_MODEL)
            }
        }.lowercase(Locale.ENGLISH)
        val vulkan = if (
            hardware.contains("adreno") ||
            hardware.contains("qcom") ||
            hardware.contains("qualcomm") ||
            hardware.contains("snapdragon")
        ) {
            GraphicsDrivers.TURNIP
        } else {
            GraphicsDrivers.DEFAULT_VULKAN_DRIVER
        }
        val opengl = if (
            hardware.contains("mali") ||
            hardware.contains("mt") ||
            hardware.contains("mediatek") ||
            hardware.contains("exynos")
        ) {
            GraphicsDrivers.VIRGL
        } else {
            GraphicsDrivers.DEFAULT_OPENGL_DRIVER
        }
        return "$vulkan,$opengl"
    }

    private fun applyPerformanceEnv(env: EnvVars, graphicsDriver: String) {
        val drivers = GraphicsDrivers.parseIdentifiers(graphicsDriver)
        env.put("BOX64_LOG", "0")
        env.put("BOX64_NOBANNER", "1")
        env.put("BOX64_DYNAREC", "1")
        env.put("BOX64_DYNAREC_FASTNAN", "1")
        env.put("BOX64_DYNAREC_FASTROUND", "1")
        env.put("BOX64_DYNAREC_BIGBLOCK", "3")
        env.put("BOX64_DYNAREC_FORWARD", "512")
        env.put("BOX64_DYNAREC_CALLRET", "1")
        env.put("BOX64_DYNAREC_NATIVEFLAGS", "1")
        env.put("BOX64_DYNAREC_WEAKBARRIER", "2")
        env.put("DXVK_LOG_LEVEL", "none")
        env.put("DXVK_STATE_CACHE_PATH", RootFS.getDosUserCachePath())
        env.put("VKD3D_SHADER_CACHE_PATH", RootFS.getDosUserCachePath())
        env.put("MESA_SHADER_CACHE_DISABLE", "false")
        env.put("MESA_GL_VERSION_OVERRIDE", "4.5")
        env.put("MESA_GLSL_VERSION_OVERRIDE", "450")
        env.put("vblank_mode", "0")

        if (drivers[0] == GraphicsDrivers.TURNIP) {
            env.put("MESA_VK_WSI_USE_HWBUF", "1")
            env.put("MESA_VK_WSI_FORCE_WAIT_FOR_FENCES", "1")
            env.put("TU_DEBUG", "noconform")
        }
        if (drivers[1] == GraphicsDrivers.VIRGL) {
            env.put("GALLIUM_DRIVER", "virpipe")
        }
    }

    private fun buildGuestCommand(path: String): String {
        val unixPath = path.removePrefix("file://")
        val exe = File(unixPath)
        val dosPath = WineUtils.unixToDOSPath(exe.absolutePath, container).ifBlank {
            "Z:${exe.absolutePath.replace("/", "\\")}"
        }
        val escaped = dosPath.replace("\"", "\\\"")
        return "wine explorer /desktop=rpgtl,${screenInfo} \"$escaped\" --remote-debugging-port=${RuntimeBridge.CDP_PORT}"
    }

    private fun prepareExecutablePath(rawPath: String, gameTitle: String): String {
        if (!rawPath.startsWith("content://", ignoreCase = true)) {
            return rawPath
        }
        val uri = Uri.parse(rawPath)
        val safeName = resolveExecutableName(uri, gameTitle)
        val targetDir = File(filesDir, "wine_exe_cache").apply { mkdirs() }
        val target = File(targetDir, safeName)
        contentResolver.openInputStream(uri)?.use { input ->
            target.outputStream().use { output -> input.copyTo(output) }
        } ?: throw IllegalStateException("Cannot read selected exe file.")
        target.setReadable(true, false)
        target.setWritable(true, true)
        return target.absolutePath
    }

    private fun resolveExecutableName(uri: Uri, fallback: String): String {
        val fromDocument = androidx.documentfile.provider.DocumentFile.fromSingleUri(this, uri)?.name.orEmpty()
        val raw = fromDocument.ifBlank {
            Uri.decode(uri.lastPathSegment ?: "").substringAfterLast('/').substringAfterLast(':')
        }.ifBlank { fallback.ifBlank { "Game.exe" } }
        val sanitized = raw.replace(Regex("""[\\/:*?"<>|]"""), "_")
        return if (sanitized.endsWith(".exe", ignoreCase = true)) sanitized else "$sanitized.exe"
    }

    private fun createDisplayLayout(gameTitle: String): View {
        val root = FrameLayout(this)
        root.addView(xServerView, FrameLayout.LayoutParams(-1, -1))
        root.addView(touchpadView, FrameLayout.LayoutParams(-1, -1))
        root.addView(inputControlsView, FrameLayout.LayoutParams(-1, -1))
        touchBlocker = View(this).apply {
            setBackgroundColor(0x00000000)
            isClickable = true
            isFocusable = false
            visibility = View.GONE
            setOnTouchListener { _, _ -> true }
        }
        root.addView(touchBlocker, FrameLayout.LayoutParams(-1, -1))
        toolbar = FloatingToolbar(this, this)
        root.addView(toolbar, floatingParams(Gravity.END or Gravity.CENTER_VERTICAL, 0, 0, 0, 0))
        root.systemUiVisibility = immersiveFlags()
        return root
    }

    private fun floatingParams(gravity: Int, left: Int, top: Int, right: Int, bottom: Int): FrameLayout.LayoutParams {
        return FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT
        ).apply {
            this.gravity = gravity
            setMargins(left, top, right, bottom)
        }
    }

    private fun immersiveFlags(): Int {
        return View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
    }

    override fun onToolbarAction(action: String) {
        when (action) {
            "runtime" -> openToolPage("runtime")
            "translate" -> openToolPage("translate")
            "data" -> openToolPage("data")
            "keyboard" -> AppUtils.showKeyboard(this)
            "touch" -> setTouchBlocked(!touchBlocked)
            "rotate" -> toggleOrientation()
            "close" -> {
                stopGame()
                finish()
            }
            else -> {
                val result = runtimeBridge.command(action).optString("error", "")
                if (result.isNotBlank()) Toast.makeText(this, result, Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun openToolPage(page: String) {
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            putExtra("target_page", page)
            putExtra("source_app", "rpgtl_wine")
            putExtra("container_id", container.id)
            putExtra("container_name", container.name)
            putExtra("game_title", intent.getStringExtra(EXTRA_GAME_TITLE).orEmpty())
            putExtra("game_path", gameExePath)
        }
        startActivity(intent)
    }

    private fun setTouchBlocked(blocked: Boolean) {
        touchBlocked = blocked
        touchBlocker?.visibility = if (blocked) View.VISIBLE else View.GONE
        toolbar?.setTouchBlocked(blocked)
        toolbar?.bringToFront()
    }

    private fun toggleOrientation() {
        val current = resources.configuration.orientation
        requestedOrientation = if (current == Configuration.ORIENTATION_LANDSCAPE) {
            ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        } else {
            ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        }
        toolbar?.postDelayed({ AppUtils.hideSystemUI(this) }, 450)
    }

    override fun onBackPressed() {
        AlertDialog.Builder(this)
            .setTitle("退出游戏")
            .setMessage("关闭后将停止 Wine 进程并释放资源。确定退出？")
            .setPositiveButton("退出") { _, _ ->
                stopGame()
                finish()
            }
            .setNegativeButton("继续游戏", null)
            .show()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            onBackPressed()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    private fun stopGame() {
        try { runtimeBridge?.disconnect() } catch (_: Exception) {}
        try { launcherComponent?.stop() } catch (_: Exception) {}
        try { environment.stopEnvironmentComponents() } catch (_: Exception) {}
        try { winHandler.stop() } catch (_: Exception) {}
        try { xServerView?.onPause() } catch (_: Exception) {}
    }

    override fun onPause() {
        // Keep Wine running when the RPGTL tool page is opened, so CDP/runtime edits stay live.
        super.onPause()
    }

    override fun onResume() {
        super.onResume()
        xServerView?.onResume()
        environment?.onResume()
        AppUtils.hideSystemUI(this)
    }

    override fun onGenericMotionEvent(event: MotionEvent): Boolean {
        return winHandler?.onGenericMotionEvent(event) == true ||
            inputControlsView?.onGenericMotionEvent(event) == true ||
            super.onGenericMotionEvent(event)
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        return inputControlsView?.onKeyEvent(event) == true ||
            winHandler?.onKeyEvent(event) == true ||
            super.dispatchKeyEvent(event)
    }

    override fun onDestroy() {
        activeRuntimeBridges.remove(container.id)
        runtimeBridge.disconnect()
        stopGame()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_GAME_URI = "game_uri"
        const val EXTRA_GAME_TITLE = "game_title"
        const val EXTRA_CONTAINER_ID = "container_id"
        const val EXTRA_BOX64_PRESET = "box64_preset"
        const val EXTRA_GRAPHICS_DRIVER = "graphics_driver"
        private const val TAG = "RPGTL-Wine"
        private val activeRuntimeBridges = ConcurrentHashMap<Int, RuntimeBridge>()

        fun runtimeBridgeFor(containerId: Int): RuntimeBridge? {
            return activeRuntimeBridges[containerId]
        }
    }
}

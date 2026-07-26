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
import android.provider.DocumentsContract
import android.util.Log
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.text.InputType
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.rpgrtl.engine.XServerDisplayActivity
import com.rpgrtl.engine.box64.Box64Preset
import com.rpgrtl.engine.container.Container
import com.rpgrtl.engine.container.ContainerManager
import com.rpgrtl.engine.container.DXWrappers
import com.rpgrtl.engine.container.GraphicsDrivers
import com.rpgrtl.engine.core.AppUtils
import com.rpgrtl.engine.core.DefaultVersion
import com.rpgrtl.engine.core.EnvVars
import com.rpgrtl.engine.core.FileUtils
import com.rpgrtl.engine.core.GeneralComponents
import com.rpgrtl.engine.core.GPUHelper
import com.rpgrtl.engine.core.ProcessHelper
import com.rpgrtl.engine.core.TarCompressorUtils
import com.rpgrtl.engine.core.WineInfo
import com.rpgrtl.engine.core.WineUtils
import com.rpgrtl.engine.alsaserver.ALSAClient
import com.rpgrtl.engine.widget.InputControlsView
import com.rpgrtl.engine.inputcontrols.Binding
import com.rpgrtl.engine.inputcontrols.ControlElement
import com.rpgrtl.engine.inputcontrols.ControlsProfile
import com.rpgrtl.engine.inputcontrols.InputControlsManager
import com.rpgrtl.engine.widget.TouchpadView
import com.rpgrtl.engine.widget.XServerView
import com.rpgrtl.engine.winhandler.WinHandler
import com.rpgrtl.engine.xconnector.UnixSocketConfig
import com.rpgrtl.engine.xenvironment.RootFS
import com.rpgrtl.engine.xenvironment.RootFSInstaller
import com.rpgrtl.engine.xenvironment.XEnvironment
import com.rpgrtl.engine.xenvironment.components.GuestProgramLauncherComponent
import com.rpgrtl.engine.xenvironment.components.ALSAServerComponent
import com.rpgrtl.engine.xenvironment.components.SysVSharedMemoryComponent
import com.rpgrtl.engine.xenvironment.components.VirGLRendererComponent
import com.rpgrtl.engine.xenvironment.components.XServerComponent
import com.rpgrtl.engine.xserver.ScreenInfo
import com.rpgrtl.engine.xserver.XServer
import com.rpgrtl.shell.MainActivity
import com.rpgrtl.shell.ShellLog
import androidx.preference.PreferenceManager
import java.io.File
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap

class WineDisplayActivity : XServerDisplayActivity(), FloatingToolbar.Listener {
    private var launcherComponent: GuestProgramLauncherComponent? = null
    private lateinit var runtimeBridge: RuntimeBridge
    private var toolbar: FloatingToolbar? = null
    private var touchBlocker: View? = null
    /** true = direct tap (hide cursor, click at finger); false = pointer mode (show cursor) */
    private var directTapMode = true
    /** Once a DOWN hits a virtual key, keep routing that gesture to InputControls until UP. */
    private var virtualKeyGestureActive = false
    private var gameExePath = ""
    private var gameWorkDir = ""
    private var selectedBox64Preset = Box64Preset.PERFORMANCE
    private var selectedGraphicsDriver = ""
    private var wineDebugCallback: com.rpgrtl.engine.core.Callback<String>? = null
    private var renpyLiveTranslationService: RenPyLiveTranslationService? = null
    private var displayRoot: FrameLayout? = null
    private var editorTopBar: View? = null
    private var editorSidePanel: View? = null
    private var editorProfileLabel: TextView? = null
    private var liveLogPanel: View? = null
    private var liveLogText: TextView? = null
    private var liveLogScroll: android.widget.ScrollView? = null
    private val liveLogRefresh = object : Runnable {
        override fun run() {
            refreshLiveLogPanel()
            liveLogPanel?.postDelayed(this, 1500)
        }
    }
    private val editorUndoStack = ArrayList<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ShellLog.installCrashLogger(this)
        ShellLog.info(this, "WineDisplayActivity onCreate")
        AppUtils.hideSystemUI(this)
        AppUtils.keepScreenOn(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE

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
            startBundledWineRuntimeInstall()
            return
        }
        WinePathCompat.ensureBridge(this)

        if (!prepareContainer(containerId, gameTitle)) return
        gameExePath = prepareExecutablePath(gameExePath, gameTitle)
        // Match Winlator's normal launch path: map the selected game directory as D:
        // and launch the exe through that drive.  Do not copy a game into the container.
        gameExePath = prepareDirectGamePath(gameExePath) ?: return
        gameWorkDir = resolveLaunchFile(gameExePath).parentFile?.absolutePath.orEmpty()
        applyLiveTranslationState(readLiveTranslationEnabled(), announce = false)

        if (!ensureWineRuntimePrepared()) return

        val dm = resources.displayMetrics
        val screenW = maxOf(dm.widthPixels, dm.heightPixels).coerceAtLeast(1280)
        val screenH = minOf(dm.widthPixels, dm.heightPixels).coerceAtLeast(720)
        val dynamicScreen = "${screenW}x${screenH}"
        container.screenSize = dynamicScreen
        screenInfo = ScreenInfo(dynamicScreen)
        ShellLog.info(this, "Wine display init screen=$dynamicScreen device=${dm.widthPixels}x${dm.heightPixels}")
        xServer = XServer(this, screenInfo)
        winHandler = WinHandler(this)
        xServer.setWinHandler(winHandler)

        xServerView = XServerView(this, xServer)
        xServer.setRenderer(xServerView.renderer)
        xServer.pointer.setPosition(screenInfo.width / 2, screenInfo.height / 2)

        touchpadView = TouchpadView(this, xServer, false).apply {
            // Default: direct tap mode (point-and-click). Toggle via side toolbar.
            setMoveCursorToTouchpoint(true)
            setSensitivity(1.35f)
            // Events are forwarded programmatically from InputControlsView / Activity.
            isClickable = false
            isFocusable = false
        }
        // Stop Wine from warping the cursor back to center / capture point every frame.
        xServer.setIgnoreGuestCursorWarp(true)
        xServer.cursorLocker.setEnabled(false)
        // Ren'Py commonly opens a fixed 1280x720 undecorated window.  Let the renderer scale
        // that window to the actual landscape X screen and transform pointer events with it.
        xServerView.renderer.setForceWindowsFullscreen(true)
        // Direct-tap default: hide on-screen cursor so it doesn't obscure UI.
        xServerView.renderer.setCursorVisible(false)
        inputControlsView = InputControlsView(this).apply {
            setXServer(xServer)
            setTouchpadView(touchpadView)
            setShowTouchscreenControls(true)
            isClickable = true
            isFocusable = true
        }
        loadDefaultControlsProfile(inputControlsView)

        environment = XEnvironment(this, rootFS)
        addRuntimeComponents()
        setContentView(createDisplayLayout(gameTitle))
        // Never leave a leftover full-screen input blocker on.
        touchBlocker?.visibility = View.GONE
        touchBlocker?.isEnabled = false
        // Always start playable (not edit mode).
        inputControlsView.setEditMode(false)
        applyInputMode(directTap = true, announce = false)
        inputControlsView.post {
            // Defensive re-wire: virtual keys must keep a non-null touchpad reference.
            inputControlsView.setTouchpadView(touchpadView)
            inputControlsView.setXServer(xServer)
            inputControlsView.setEditMode(false)
            touchpadView.isEnabled = true
            touchpadView.setMoveCursorToTouchpoint(directTapMode)
            // Force-load virtual key layout now that view has real size.
            try {
                val p = inputControlsView.profile
                if (p != null) {
                    p.loadElements(inputControlsView)
                    ShellLog.info(
                        this,
                        "Controls profile loaded name=${p.name} elements=${p.elements.size} " +
                            "file=${com.rpgrtl.engine.inputcontrols.ControlsProfile.getProfileFile(this, p.id).absolutePath} " +
                            "exists=${com.rpgrtl.engine.inputcontrols.ControlsProfile.getProfileFile(this, p.id).isFile}"
                    )
                } else {
                    ShellLog.info(this, "Controls profile is null after setProfile")
                }
            } catch (error: Throwable) {
                ShellLog.error(this, "Force loadElements failed", error)
            }
            inputControlsView.bringToFront()
            toolbar?.bringToFront()
            inputControlsView.invalidate()
            ShellLog.info(
                this,
                "Input ready layout=${inputControlsView.width}x${inputControlsView.height} " +
                    "screen=${screenInfo.width}x${screenInfo.height} mode=" +
                    (if (directTapMode) "direct" else "pointer") +
                    " editMode=${inputControlsView.isEditMode}" +
                    " touchpadNull=${inputControlsView.touchpadView == null}" +
                    " xServerNull=${inputControlsView.xServer == null}"
            )
        }

        winHandler.start()
        wineDebugCallback?.let { ProcessHelper.removeDebugCallback(it) }
        wineDebugCallback = com.rpgrtl.engine.core.Callback<String> { line ->
            ShellLog.info(this, "Wine output: $line")
        }.also { ProcessHelper.addDebugCallback(it) }
        environment.startEnvironmentComponents()
        activeRuntimeBridges[container.id] = runtimeBridge
        Handler(Looper.getMainLooper()).postDelayed({
            val box64 = File(rootFS.rootDir, "usr/local/bin/box64")
            val wineBin = File(rootFS.rootDir, "opt/wine/bin/wine")
            ShellLog.info(
                this,
                "Starting Wine guest once cmd=${launcherComponent?.guestExecutable} " +
                    "cwd=${launcherComponent?.workingDir} box64=${box64.absolutePath} " +
                    "box64Exists=${box64.isFile} box64Size=${box64.length()} " +
                    "wineExists=${wineBin.isFile} bridge=${WinePathCompat.ensureBridge(this)}"
            )
            launcherComponent?.start()
            ShellLog.info(this, "launcherComponent.start() pid=${launcherComponent?.pid ?: -1}")
        }, 1200)

        Toast.makeText(this, "正在通过 Wine + Box64 启动：$gameTitle", Toast.LENGTH_LONG).show()
    }

    private fun startBundledWineRuntimeInstall() {
        ShellLog.info(this, "Wine RootFS missing; installing bundled Winlator runtime")
        setContentView(FrameLayout(this).apply {
            setBackgroundColor(0xFF000000.toInt())
            systemUiVisibility = immersiveFlags()
        })
        Toast.makeText(this, "首次启动正在初始化内置 Winlator/Wine 环境，请稍等一次。", Toast.LENGTH_LONG).show()

        Thread {
            val ok = installBundledWineRuntime()
            runOnUiThread {
                if (ok) {
                    ShellLog.info(this, "Bundled Winlator runtime installed; restarting WineDisplayActivity")
                    Toast.makeText(this, "内置 Winlator/Wine 环境已初始化，正在启动游戏。", Toast.LENGTH_SHORT).show()
                    recreate()
                } else {
                    Toast.makeText(this, "内置 Winlator/Wine 环境初始化失败，请查看运行日志。", Toast.LENGTH_LONG).show()
                    finish()
                }
            }
        }.start()
    }

    private fun installBundledWineRuntime(): Boolean {
        return try {
            val rootDir = rootFS.rootDir
            ShellLog.info(this, "Extracting bundled rootfs to ${rootDir.absolutePath}")
            FileUtils.delete(rootDir)
            rootDir.mkdirs()
            val ok = TarCompressorUtils.extract(
                TarCompressorUtils.Type.ZSTD,
                this,
                "winlator/rootfs.tzst",
                rootDir
            )
            if (ok) {
                rootFS.createRFSVersionFile(RootFSInstaller.LATEST_VERSION.toInt())
            }
            val valid = ok && rootFS.isValid
            ShellLog.info(this, "Bundled rootfs install result ok=$ok valid=$valid version=${rootFS.version}")
            valid
        } catch (error: Throwable) {
            Log.e(TAG, "Bundled Wine runtime install failed", error)
            ShellLog.error(this, "Bundled Wine runtime install failed", error)
            false
        }
    }

    private fun prepareContainer(containerId: Int, gameTitle: String): Boolean {
        val manager = ContainerManager(this)
        container = if (containerId > 0) {
            manager.getContainerById(containerId)
        } else {
            manager.containers.firstOrNull() ?: manager.ensureDefaultContainer(gameTitle)
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
        container.setDXWrapper(DXWrappers.WINED3D)
        container.setStartupSelection(Container.STARTUP_SELECTION_ESSENTIAL)
        Log.i(TAG, "Wine launch profile: box64=$selectedBox64Preset graphics=$selectedGraphicsDriver")
        manager.activateContainer(container)
        WineUtils.createDosdevicesSymlinks(container, false)
        return true
    }

    /**
     * Winlator's rootfs is not usable as a Wine runtime straight after extraction.  It needs
     * its binary path patches and guest drivers before wineserver can be spawned.
     */
    private fun ensureWineRuntimePrepared(): Boolean {
        val marker = File(rootFS.rootDir, ".winlator/rpgtl_runtime_prepared_v3")
        if (marker.isFile) {
            WinePathCompat.ensureBridge(this)
            WinePathCompat.patchBox64Interpreter(this)
            return true
        }

        setContentView(FrameLayout(this).apply {
            setBackgroundColor(0xFF000000.toInt())
            systemUiVisibility = immersiveFlags()
        })
        Toast.makeText(this, "正在初始化内置 Winlator 运行环境，请稍候…", Toast.LENGTH_LONG).show()
        Thread {
            val ok = runCatching { prepareWineRuntime(marker) }
                .onFailure { ShellLog.error(this, "Wine runtime preparation failed", it) }
                .isSuccess
            runOnUiThread {
                if (ok) {
                    ShellLog.info(this, "Winlator runtime preparation complete; restarting display")
                    recreate()
                } else {
                    Toast.makeText(this, "Winlator 运行环境初始化失败，请查看运行日志", Toast.LENGTH_LONG).show()
                    finish()
                }
            }
        }.start()
        return false
    }

    private fun prepareWineRuntime(marker: File) {
        val rootDir = rootFS.rootDir
        val drivers = GraphicsDrivers.parseIdentifiers(selectedGraphicsDriver)
        ShellLog.info(this, "Preparing Winlator runtime vulkan=${drivers[0]} opengl=${drivers[1]}")
        WinePathCompat.ensureBridge(this)

        TarCompressorUtils.extract(TarCompressorUtils.Type.ZSTD, this, "winlator/rootfs_patches.tzst", rootDir)
        GeneralComponents.extractFile(GeneralComponents.Type.BOX64, this, DefaultVersion.BOX64, DefaultVersion.BOX64)
        val box64 = File(rootDir, "usr/local/bin/box64")
        FileUtils.chmod(box64, 0b111_101_101)
        PreferenceManager.getDefaultSharedPreferences(this).edit()
            .putString("current_box64_version", DefaultVersion.BOX64)
            .putString("box64_version", DefaultVersion.BOX64)
            .apply()

        val openglVersion = when (drivers[1]) {
            GraphicsDrivers.VIRGL -> DefaultVersion.VIRGL
            GraphicsDrivers.ZINK -> DefaultVersion.ZINK
            else -> DefaultVersion.GLADIO
        }
        GeneralComponents.extractGraphicsDriverAsset(this, drivers[1], openglVersion)
        if (drivers[1] != GraphicsDrivers.GLADIO) {
            GeneralComponents.extractGraphicsDriverAsset(this, GraphicsDrivers.GLADIO, DefaultVersion.GLADIO)
        }
        val vulkanVersion = if (drivers[0] == GraphicsDrivers.VORTEK) DefaultVersion.VORTEK else DefaultVersion.TURNIP
        GeneralComponents.extractGraphicsDriverAsset(this, drivers[0], vulkanVersion)
        GeneralComponents.extractFile(GeneralComponents.Type.DXVK, this, DefaultVersion.DXVK(drivers[0]), DefaultVersion.MAJOR_DXVK)

        WineUtils.applySystemTweaks(this, WineInfo.MAIN_WINE_INFO)
        WineUtils.changeServicesStatus(container, true)
        val corePatches = WinePathCompat.patchCoreRuntimePaths(this)
        val box64Ok = WinePathCompat.patchBox64Interpreter(this)
        val gladioOk = WinePathCompat.patchGuestGladio(this)
        check(box64Ok) { "box64 interpreter patch failed" }
        marker.parentFile?.mkdirs()
        FileUtils.writeString(marker, System.currentTimeMillis().toString())
        ShellLog.info(this, "Winlator runtime ready corePatches=$corePatches box64=$box64Ok gladio=$gladioOk")
    }

    private fun loadDefaultControlsProfile(view: InputControlsView) {
        val manager = InputControlsManager(this)
        ensureRenPyProfileHasCursorControls(manager)
        val profiles = manager.getProfiles(true)
        val profile = profiles.firstOrNull { it.name.contains("RenPy", ignoreCase = true) }
            ?: profiles.firstOrNull { it.name.contains("Visual Novel", ignoreCase = true) }
            ?: profiles.firstOrNull()
        if (profile != null) {
            // Element coordinates in .icp are fractions of the overlay's measured size.
            // Loading here (before setContentView/layout) used a 0x0 view and placed every
            // control at (0,0). InputControlsView loads the elements on its first draw,
            // after it has the actual landscape dimensions.
            view.setProfile(profile)
            Log.i(TAG, "Queued touchscreen controls profile: ${profile.name}")
        } else {
            Log.w(TAG, "No touchscreen controls profile found; virtual controls will be empty.")
        }
    }

    /**
     * Point-and-click migration: remove the large TRACKPAD overlay that ate full-screen
     * touches, and ensure scroll buttons exist.  Whole-screen absolute touchpad replaces it.
     */
    private fun ensureRenPyProfileHasCursorControls(manager: InputControlsManager) {
        val prefs = PreferenceManager.getDefaultSharedPreferences(this)
        if (prefs.getBoolean("renpy_touch_absolute_v1", false)) return
        try {
            val profile = manager.getProfiles(true)
                .firstOrNull { it.name.contains("RenPy", ignoreCase = true) }
                ?: return
            val file = ControlsProfile.getProfileFile(this, profile.id)
            if (!file.isFile) return
            val data = org.json.JSONObject(FileUtils.readString(file))
            val elements = data.optJSONArray("elements") ?: org.json.JSONArray()
            val next = org.json.JSONArray()
            var hasScroll = false
            var removedTrackpad = false
            for (i in 0 until elements.length()) {
                val el = elements.getJSONObject(i)
                if (el.optString("type") == "TRACKPAD") {
                    removedTrackpad = true
                    continue
                }
                val bindings = el.optJSONArray("bindings")
                if (bindings != null) {
                    for (j in 0 until bindings.length()) {
                        val b = bindings.optString(j)
                        if (b == "MOUSE_SCROLL_UP" || b == "MOUSE_SCROLL_DOWN") hasScroll = true
                    }
                }
                next.put(el)
            }
            if (!hasScroll) {
                next.put(
                    org.json.JSONObject()
                        .put("type", "BUTTON")
                        .put("shape", "ROUND_RECT")
                        .put("bindings", org.json.JSONArray().put("MOUSE_SCROLL_UP"))
                        .put("scale", 0.68)
                        .put("opacity", 0.7)
                        .put("x", 0.94)
                        .put("y", 0.40)
                        .put("toggleSwitch", false)
                        .put("text", "▲")
                        .put("iconId", 0)
                )
                next.put(
                    org.json.JSONObject()
                        .put("type", "BUTTON")
                        .put("shape", "ROUND_RECT")
                        .put("bindings", org.json.JSONArray().put("MOUSE_SCROLL_DOWN"))
                        .put("scale", 0.68)
                        .put("opacity", 0.7)
                        .put("x", 0.94)
                        .put("y", 0.54)
                        .put("toggleSwitch", false)
                        .put("text", "▼")
                        .put("iconId", 0)
                )
            }
            data.put("elements", next)
            data.put("cursorSpeed", 1.25)
            FileUtils.writeString(file, data.toString())
            Log.i(TAG, "RenPy absolute-touch migration removedTrackpad=$removedTrackpad hasScroll=$hasScroll")
            prefs.edit()
                .putBoolean("renpy_touch_absolute_v1", true)
                .putBoolean("renpy_controls_cursor_v2", true)
                .apply()
        } catch (error: Throwable) {
            Log.w(TAG, "RenPy absolute-touch migration skipped", error)
        }
    }

    private fun addRuntimeComponents() {
        WinePathCompat.ensureBridge(this)
        val rootDir = rootFS.rootDir
        val drivers = GraphicsDrivers.parseIdentifiers(selectedGraphicsDriver)
        val guestRoot = WinePathCompat.newRootfsPrefix(this)

        File(rootDir, "tmp/.X11-unix").mkdirs()
        File(rootDir, "tmp/.sound").mkdirs()
        File(rootDir, "tmp/.sysvshm").mkdirs()
        File(rootDir, "tmp/shm").mkdirs()
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
        if (drivers[1] == GraphicsDrivers.VIRGL) {
            environment.addComponent(
                VirGLRendererComponent(
                    xServer,
                    UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.VIRGL_SERVER_PATH)
                )
            )
        }
        environment.addComponent(
            ALSAServerComponent(
                UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.ALSA_SERVER_PATH),
                ALSAClient.Options()
            )
        )

        val env = EnvVars(container.envVars)
        val winePrefix = File(container.rootDir, ".wine").absolutePath
        env.put("WINEPREFIX", winePrefix)
        env.put("HOME", rootDir.absolutePath + RootFS.HOME_PATH)
        env.put("TMPDIR", "$guestRoot/tmp")
        env.put("TEMP", "$guestRoot/tmp")
        env.put("TMP", "$guestRoot/tmp")
        env.put("DISPLAY", ":0")
        env.put("ANDROID_ALSA_SERVER", "$guestRoot${UnixSocketConfig.ALSA_SERVER_PATH}")
        env.put("ANDROID_SYSVSHM_SERVER", "$guestRoot${UnixSocketConfig.SYSVSHM_SERVER_PATH}")
        env.put("ALSA_PLUGIN_DIR", "$guestRoot/usr/lib/alsa-lib")
        env.put("SDL_AUDIODRIVER", "alsa")
        env.put("WINEDLLOVERRIDES", "winemenubuilder.exe=d;mscoree,mshtml=")
        env.put("NWJS_ARGS", "--remote-debugging-port=${RuntimeBridge.CDP_PORT}")
        env.put("CHROME_REMOTE_DEBUGGING_PORT", RuntimeBridge.CDP_PORT.toString())
        applyPerformanceEnv(env, selectedGraphicsDriver)

        val launchFile = resolveLaunchFile(gameExePath)
        ShellLog.info(
            this,
            "Wine launch executable path=${launchFile.absolutePath} exists=${launchFile.isFile} cwd=${launchFile.parentFile?.absolutePath} " +
                "prefix=$winePrefix x11=${WinePathCompat.newX11Path(this)}"
        )

        launcherComponent = GuestProgramLauncherComponent().apply {
            setEnvVars(env)
            setBox64Preset(selectedBox64Preset)
            setGuestExecutable(buildGuestCommand(launchFile))
            setWorkingDir(launchFile.parentFile)
            setDeferredStart(true)
            setTerminationCallback { status ->
                ShellLog.info(this@WineDisplayActivity, "Wine launcher exited status=$status")
                wineDebugCallback?.let { callback -> ProcessHelper.removeDebugCallback(callback) }
                wineDebugCallback = null
                runOnUiThread {
                    Toast.makeText(this@WineDisplayActivity, "Wine 启动器异常结束（code=$status）。", Toast.LENGTH_SHORT).show()
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
        // This Android build has no compatible POSIX shared-memory backend for esync.
        // Enabling it makes wineserver fail with shm_open/ftruncate errors before the game starts.
        env.put("WINEESYNC", "0")
        val drivers = GraphicsDrivers.parseIdentifiers(graphicsDriver)
        // Wine errors remain in the app log; suppress Box64's repetitive loader trace.
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
        // SDL2/Ren'Py is substantially more compatible with the Winlator gladio 3.3 path.
        env.put("MESA_GL_VERSION_OVERRIDE", "3.3")
        env.put("MESA_GLSL_VERSION_OVERRIDE", "330")
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

    private fun resolveLaunchFile(path: String): File {
        val resolvedPath = if (path.startsWith("file://", ignoreCase = true)) {
            Uri.parse(path).path.orEmpty()
        } else if (path.startsWith("content://", ignoreCase = true)) {
            resolveExternalStorageDocumentFile(Uri.parse(path))?.absolutePath ?: path
        } else {
            path
        }
        return File(resolvedPath)
    }

    /**
     * Ren'Py windows builds often expose lib/py3-windows-x86_64/python.exe.
     * Launching that alone fails with missing encodings/PYTHONHOME.
     * Prefer the game root launcher next to game/ + renpy/.
     */
    private fun resolveRenPyLaunchTarget(selected: File): File {
        if (!selected.isFile) return selected
        val projectRoot = findRenPyProjectRoot(selected) ?: return selected
        val rootExes = projectRoot.listFiles()
            ?.filter {
                it.isFile &&
                    it.extension.equals("exe", true) &&
                    !it.name.equals("python.exe", true) &&
                    !it.name.equals("pythonw.exe", true) &&
                    !it.name.equals("renpy.exe", true)
            }
            .orEmpty()
        if (rootExes.isEmpty()) return selected

        val preferredNames = listOf(
            projectRoot.name,
            gameTitleHint(),
            "game",
        ).map { it.trim().lowercase(Locale.ROOT) }.filter { it.isNotBlank() }

        val preferred = rootExes.firstOrNull { exe ->
            val base = exe.nameWithoutExtension.lowercase(Locale.ROOT)
            preferredNames.any { name -> base == name || base.contains(name) || name.contains(base) }
        }
        val launcher = preferred ?: rootExes.minByOrNull { it.name.length } ?: selected
        if (launcher.absolutePath != selected.absolutePath) {
            ShellLog.info(
                this,
                "RenPy launcher remap selected=${selected.absolutePath} -> ${launcher.absolutePath} root=${projectRoot.absolutePath}"
            )
        }
        return launcher
    }

    private fun findRenPyProjectRoot(start: File): File? {
        var current: File? = if (start.isDirectory) start else start.parentFile
        var depth = 0
        while (current != null && depth < 8) {
            val gameDir = File(current, "game")
            val renpyDir = File(current, "renpy")
            val hasScripts = gameDir.isDirectory && (
                renpyDir.isDirectory ||
                    gameDir.listFiles()?.any {
                        it.isFile && (it.extension.equals("rpy", true) || it.extension.equals("rpyc", true))
                    } == true
                )
            if (hasScripts) return current
            current = current.parentFile
            depth++
        }
        return null
    }

    private fun gameTitleHint(): String {
        return intent.getStringExtra(EXTRA_GAME_TITLE).orEmpty()
    }

    private fun buildGuestCommand(exe: File): String {
        val rootPath = rootFS.rootDir.absolutePath.trimEnd('/')
        val dosPath = if (exe.absolutePath.startsWith("$rootPath/")) {
            // Z: is the rootfs. drive_game is an ASCII symlink to the selected game folder.
            "Z:\\" + exe.absolutePath.removePrefix(rootPath).trimStart('/').replace('/', '\\')
        } else {
            val convertedDosPath = WineUtils.unixToDOSPath(exe.absolutePath, container)
            if (convertedDosPath.isBlank() || convertedDosPath == "\\") {
                "Z:${exe.absolutePath.replace("/", "\\")}"
            } else {
                convertedDosPath
            }
        }
        // Pass the executable as a single argv item.  Wine accepts this directly, whereas
        // cmd.exe mishandles escaped quotes around Chinese paths on this build.
        val command = "wine \"$dosPath\""
        ShellLog.info(this, "Wine guest command directExe=$dosPath")
        return command
    }

    /**
     * Maps the selected game folder to Wine's D: drive, exactly as a Winlator container
     * drive does.  Android's all-files grant is required because Wine is a native child
     * process and cannot consume a SAF content:// grant directly.
     */
    private fun prepareDirectGamePath(path: String): String? {
        if (!hasAllFilesAccess()) {
            ShellLog.info(this, "Wine launch needs all-files access; opening system settings")
            Toast.makeText(this, "请在系统页面开启「允许访问所有文件」，然后重新启动游戏。", Toast.LENGTH_LONG).show()
            runCatching {
                startActivity(Intent(android.provider.Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                    data = Uri.parse("package:$packageName")
                })
            }
            finish()
            return null
        }

        val selected = resolveLaunchFile(path)
        val exe = resolveRenPyLaunchTarget(selected)
        val projectRoot = findRenPyProjectRoot(exe) ?: exe.parentFile
        val gameDir = projectRoot
        if (!exe.isFile || gameDir == null || !gameDir.isDirectory) {
            ShellLog.error(this, "Wine game source is unavailable: $path")
            Toast.makeText(this, "找不到完整的游戏目录。请在游戏文件夹内选择 exe。", Toast.LENGTH_LONG).show()
            finish()
            return null
        }

        // Keep E: as the device's primary storage and use D: for the active title.
        // Container.drives has a compact parser: the next drive letter itself is the
        // delimiter.  Do not insert a separating space, or it becomes part of D:'s path.
        // For Ren'Py, D: must be the project root (game/, renpy/, launcher.exe), not lib/python.
        container.drives = "D:${gameDir.absolutePath}E:${AppUtils.INTERNAL_STORAGE}"
        container.saveData()
        WineUtils.createDosdevicesSymlinks(container, false)
        ShellLog.info(this, "Wine direct mount D:=${gameDir.absolutePath} exe=${exe.name}")
        return exe.absolutePath
    }

    private fun hasAllFilesAccess(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            android.os.Environment.isExternalStorageManager()
        } else {
            checkSelfPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE) ==
                android.content.pm.PackageManager.PERMISSION_GRANTED
        }
    }

    /**
     * Copy the selected game directory into C: once.  Wine/Box64 runs in the app-private
     * namespace and cannot reliably traverse Android external-storage symlinks, even when
     * Java can read them.  A cache marker makes subsequent launches immediate.
     */
    private fun cacheGameForWine(path: String, gameTitle: String): String? {
        val sourceExe = resolveLaunchFile(path)
        val sourceDir = sourceExe.parentFile
        if (!sourceExe.isFile || sourceDir == null || !sourceDir.isDirectory) {
            ShellLog.error(this, "Wine game source is unavailable: $path")
            Toast.makeText(this, "找不到完整的游戏目录。请在游戏文件夹内选择 exe。", Toast.LENGTH_LONG).show()
            finish()
            return null
        }

        val gameKey = Integer.toHexString(sourceDir.absolutePath.hashCode())
        val cacheRoot = File(container.rootDir, ".wine/drive_c/users/${RootFS.USER}/Games")
        val cacheDir = File(cacheRoot, "game_$gameKey")
        var cachedExe = File(cacheDir, sourceExe.name)
        val marker = File(cacheDir, ".rpgtl-source")
        val sourceStamp = "${sourceDir.absolutePath}\n${sourceExe.name}\n${sourceExe.length()}\n${sourceExe.lastModified()}"
        if (cachedExe.isFile && marker.isFile && FileUtils.readString(marker) == sourceStamp) {
            ShellLog.info(this, "Wine game cache ready exe=C:\\users\\${RootFS.USER}\\Games\\${cacheDir.name}\\${sourceExe.name}")
            return cachedExe.absolutePath
        }

        setContentView(FrameLayout(this).apply {
            setBackgroundColor(0xFF000000.toInt())
            systemUiVisibility = immersiveFlags()
        })
        Toast.makeText(this, "正在准备游戏文件（首次启动仅一次）…", Toast.LENGTH_LONG).show()
        ShellLog.info(this, "Wine game cache preparing name=$gameTitle")
        Thread {
            val result = runCatching {
                if (cacheDir.exists() && !FileUtils.delete(cacheDir)) {
                    error("Cannot replace incomplete game cache")
                }
                // /storage/emulated is itself a symlink. FileUtils deliberately skips
                // symlinks, which made it report success without copying any game file.
                check(copyGameTree(sourceDir, cacheDir)) { "Cannot copy game directory" }
                // SAF may grant the selected document while directory enumeration omits that
                // same file. Copy the explicitly selected exe independently in that case.
                if (!cachedExe.isFile) {
                    check(copyGameTree(sourceExe, cachedExe)) { "Cannot copy selected exe" }
                }
                cachedExe = findCachedExecutable(cacheDir, sourceExe.name)
                    ?: error("Cached exe is missing; entries=${cacheDir.list()?.joinToString(limit = 8).orEmpty()}")
                check(FileUtils.writeString(marker, sourceStamp)) { "Cannot write game cache marker" }
                cachedExe.absolutePath
            }
            runOnUiThread {
                result.onSuccess { cachedPath ->
                    ShellLog.info(this, "Wine game cache ready bytes=${cachedExe.length()} exe=${cachedExe.name}")
                    intent.putExtra(EXTRA_GAME_URI, cachedPath)
                    recreate()
                }.onFailure { error ->
                    ShellLog.error(this, "Wine game cache preparation failed", error)
                    Toast.makeText(this, "游戏文件准备失败，请查看运行日志。", Toast.LENGTH_LONG).show()
                    finish()
                }
            }
        }.start()
        return null
    }

    /** Copies external-storage trees while dereferencing Android's /storage symlink. */
    private fun copyGameTree(source: File, target: File): Boolean {
        return if (source.isDirectory) {
            if (!target.exists() && !target.mkdirs()) return false
            val children = source.listFiles() ?: return false
            children.all { child -> copyGameTree(child, File(target, child.name)) }
        } else {
            val parent = target.parentFile ?: return false
            if (!parent.exists() && !parent.mkdirs()) return false
            runCatching {
                source.inputStream().buffered().use { input ->
                    target.outputStream().buffered().use { output -> input.copyTo(output) }
                }
                target.setReadable(true, false)
                target.length() == source.length()
            }.getOrDefault(false)
        }
    }

    /** Android document providers may introduce one extra directory level while enumerating. */
    private fun findCachedExecutable(directory: File, name: String, depth: Int = 3): File? {
        val direct = File(directory, name)
        if (direct.isFile) return direct
        if (depth <= 0) return null
        return directory.listFiles()
            ?.asSequence()
            ?.filter { it.isDirectory }
            ?.mapNotNull { findCachedExecutable(it, name, depth - 1) }
            ?.firstOrNull()
    }

    private fun prepareExecutablePath(rawPath: String, gameTitle: String): String {
        if (!rawPath.startsWith("content://", ignoreCase = true)) {
            return rawPath
        }
        val uri = Uri.parse(rawPath)
        val directFile = resolveExternalStorageDocumentFile(uri)
        if (directFile != null) {
            ShellLog.info(this, "Direct mount content uri as file path=${directFile.absolutePath} exists=${directFile.isFile}")
            return directFile.absolutePath
        }
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

    private fun resolveExternalStorageDocumentFile(uri: Uri): File? {
        if (uri.authority != "com.android.externalstorage.documents") return null
        val documentId = runCatching {
            DocumentsContract.getDocumentId(uri)
        }.getOrElse {
            Uri.decode(uri.lastPathSegment.orEmpty())
                .substringAfter("document/", "")
                .substringAfter("tree/", "")
        }
        if (!documentId.startsWith("primary:", ignoreCase = true)) return null
        val relativePath = documentId.substringAfter(':').trimStart('/')
        if (relativePath.isBlank()) return null
        return File("/storage/emulated/0", relativePath)
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
        displayRoot = root
        root.addView(xServerView, FrameLayout.LayoutParams(-1, -1))
        root.addView(touchpadView, FrameLayout.LayoutParams(-1, -1))
        root.addView(inputControlsView, FrameLayout.LayoutParams(-1, -1))
        // touchBlocker is kept only as a legacy no-op layer (always GONE).
        // Input mode is handled by TouchpadView direct/pointer modes, not by blocking.
        touchBlocker = View(this).apply {
            setBackgroundColor(0x00000000)
            isClickable = false
            isFocusable = false
            visibility = View.GONE
            isEnabled = false
        }
        root.addView(touchBlocker, FrameLayout.LayoutParams(-1, -1))
        toolbar = FloatingToolbar(this, this).also {
            it.setLiveTranslationEnabled(readLiveTranslationEnabled())
            it.setDirectTapMode(directTapMode)
        }
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
            "live_translation" -> toggleLiveTranslation()
            "live_log" -> toggleLiveLogPanel()
            "runtime" -> openToolPage("runtime")
            "translate" -> openToolPage("translate")
            "data" -> openToolPage("data")
            "keyboard" -> AppUtils.showKeyboard(this)
            "controls" -> showControlsEditorMenu()
            "touch" -> applyInputMode(directTap = !directTapMode, announce = true)
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

    private fun toggleLiveTranslation() {
        val enabled = !readLiveTranslationEnabled()
        writeLiveTranslationEnabled(enabled)
        applyLiveTranslationState(enabled, announce = true)
    }

    private fun readLiveTranslationEnabled(): Boolean {
        val raw = getSharedPreferences(MainActivity::class.java.simpleName, MODE_PRIVATE)
            .getString("launch_settings_json", "")
            .orEmpty()
        if (raw.isBlank()) return true
        return runCatching {
            val root = org.json.JSONObject(raw)
            val renpy = root.optJSONObject("game")?.optJSONObject("renpy")
                ?: root.optJSONObject("renpy")
                ?: org.json.JSONObject()
            renpy.optBoolean("liveTranslation", true)
        }.getOrDefault(true)
    }

    private fun writeLiveTranslationEnabled(enabled: Boolean) {
        val prefs = getSharedPreferences(MainActivity::class.java.simpleName, MODE_PRIVATE)
        val raw = prefs.getString("launch_settings_json", "").orEmpty()
        val root = runCatching {
            if (raw.isBlank()) org.json.JSONObject() else org.json.JSONObject(raw)
        }.getOrDefault(org.json.JSONObject())
        val game = root.optJSONObject("game") ?: org.json.JSONObject()
        val renpy = game.optJSONObject("renpy") ?: root.optJSONObject("renpy") ?: org.json.JSONObject()
        renpy.put("liveTranslation", enabled)
        game.put("renpy", renpy)
        root.put("game", game)
        root.put("renpy", renpy)
        prefs.edit().putString("launch_settings_json", root.toString()).apply()
    }

    private fun applyLiveTranslationState(enabled: Boolean, announce: Boolean) {
        toolbar?.setLiveTranslationEnabled(enabled)
        if (!enabled) {
            renpyLiveTranslationService?.stop()
            renpyLiveTranslationService = null
            if (announce) {
                Toast.makeText(this, "实时汉化已关闭（重新进游戏后完全生效）", Toast.LENGTH_SHORT).show()
            }
            return
        }
        val root = gameWorkDir.takeIf { it.isNotBlank() }?.let { File(it) }
            ?: resolveLaunchFile(gameExePath).parentFile
        if (root == null || !root.isDirectory) {
            if (announce) Toast.makeText(this, "未找到游戏目录，无法开启实时汉化", Toast.LENGTH_SHORT).show()
            return
        }
        if (renpyLiveTranslationService == null) {
            RenPyLiveTranslationService(this, root).let { service ->
                if (service.installAndStart()) {
                    renpyLiveTranslationService = service
                } else if (announce) {
                    Toast.makeText(this, "实时汉化开启失败，请查看运行日志", Toast.LENGTH_SHORT).show()
                    toolbar?.setLiveTranslationEnabled(false)
                    return
                }
            }
        }
        if (announce) {
            Toast.makeText(this, "实时汉化已开启", Toast.LENGTH_SHORT).show()
        }
    }

    private fun toggleLiveLogPanel() {
        val root = displayRoot ?: return
        val existing = liveLogPanel
        if (existing != null && existing.visibility == View.VISIBLE) {
            existing.visibility = View.GONE
            existing.removeCallbacks(liveLogRefresh)
            liveLogScroll?.removeCallbacks(liveLogRefresh)
            return
        }
        if (liveLogPanel == null) {
            liveLogPanel = buildLiveLogPanel().also { panel ->
                val density = resources.displayMetrics.density
                root.addView(
                    panel,
                    FrameLayout.LayoutParams((520 * density).toInt(), FrameLayout.LayoutParams.MATCH_PARENT).apply {
                        gravity = Gravity.START or Gravity.CENTER_VERTICAL
                        setMargins((8 * density).toInt(), (8 * density).toInt(), 0, (8 * density).toInt())
                    }
                )
            }
        }
        liveLogPanel?.visibility = View.VISIBLE
        liveLogPanel?.bringToFront()
        toolbar?.bringToFront()
        refreshLiveLogPanel()
        liveLogPanel?.removeCallbacks(liveLogRefresh)
        liveLogPanel?.postDelayed(liveLogRefresh, 1500)
    }

    private fun buildLiveLogPanel(): View {
        val density = resources.displayMetrics.density
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((12 * density).toInt(), (10 * density).toInt(), (12 * density).toInt(), (10 * density).toInt())
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(0xEE07111F.toInt())
                setStroke((1 * density).toInt(), 0x664DD6C8)
            }
            elevation = 14 * density
            isClickable = true
            isFocusable = true
        }
        val title = TextView(this).apply {
            text = "实时汉化日志"
            setTextColor(0xFFF8FAFC.toInt())
            textSize = 15f
            setPadding(0, 0, 0, (8 * density).toInt())
        }
        val close = TextView(this).apply {
            text = "关闭"
            gravity = Gravity.CENTER
            setTextColor(0xFF06111C.toInt())
            textSize = 12f
            setPadding((10 * density).toInt(), (7 * density).toInt(), (10 * density).toInt(), (7 * density).toInt())
            background = android.graphics.drawable.GradientDrawable().apply { setColor(0xFF4DD6C8.toInt()) }
            isClickable = true
            isFocusable = true
            setOnClickListener { hideLiveLogPanel() }
        }
        val head = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(title, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            addView(close, LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        }
        liveLogText = TextView(this).apply {
            setTextColor(0xFFDCEBFF.toInt())
            textSize = 11f
            typeface = android.graphics.Typeface.MONOSPACE
            setLineSpacing(0f, 1.15f)
        }
        val scroll = android.widget.ScrollView(this).apply {
            isFillViewport = false
            isClickable = true
            isFocusable = true
            isNestedScrollingEnabled = true
            addView(liveLogText)
        }
        liveLogScroll = scroll
        panel.addView(head)
        panel.addView(scroll, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        return panel
    }

    private fun hideLiveLogPanel() {
        liveLogPanel?.visibility = View.GONE
        liveLogPanel?.removeCallbacks(liveLogRefresh)
        liveLogScroll?.removeCallbacks(liveLogRefresh)
    }

    private fun refreshLiveLogPanel() {
        val raw = RenPyLiveTranslationService.currentStatus()
        val text = runCatching {
            val obj = org.json.JSONObject(raw)
            val recent = obj.optJSONArray("recent") ?: org.json.JSONArray()
            buildString {
                appendLine("状态: ${obj.optString("message", "-")}")
                appendLine("Hook: ${if (obj.optBoolean("connected")) "已连接" else "未连接"}  捕获: ${obj.optInt("captured")}  已翻译: ${obj.optInt("translated")}")
                appendLine("缓存: ${obj.optInt("cached")}  队列: ${obj.optInt("queue")}  并发: ${obj.optInt("inflight")}  失败: ${obj.optInt("failures")}")
                val cooldown = obj.optLong("cooldownMs", 0L)
                if (cooldown > 0) appendLine("冷却: ${cooldown / 1000}s")
                appendLine("------------------------------")
                for (i in 0 until recent.length()) appendLine(recent.optString(i))
            }
        }.getOrElse { raw }
        if (liveLogText?.text?.toString() != text) {
            liveLogText?.text = text
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

    /**
     * Input mode:
     * - directTap=true  → 直接点: hide cursor, finger position = click target
     * - directTap=false → 指针:   show cursor, swipe moves cursor, tap clicks at cursor
     */
    private fun applyInputMode(directTap: Boolean, announce: Boolean) {
        directTapMode = directTap
        // Never block the full screen — that was the old broken "关触摸" behavior.
        touchBlocker?.visibility = View.GONE
        touchBlocker?.isEnabled = false
        touchpadView?.let { pad ->
            pad.isEnabled = true
            pad.setMoveCursorToTouchpoint(directTap)
            // Pointer mode needs slightly higher sensitivity for comfortable swipes.
            pad.setSensitivity(if (directTap) 1.25f else 1.6f)
        }
        xServerView?.renderer?.setCursorVisible(!directTap)
        xServer?.setIgnoreGuestCursorWarp(true)
        xServer?.cursorLocker?.setEnabled(false)
        toolbar?.setDirectTapMode(directTap)
        toolbar?.bringToFront()
        if (announce) {
            val msg = if (directTap) {
                "直接点击：点哪里就点哪里（指针已隐藏）"
            } else {
                "指针模式：滑动移动指针，轻点 = 在指针位置左键"
            }
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
            ShellLog.info(this, "Input mode -> ${if (directTap) "direct" else "pointer"}")
        }
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
        try {
            renpyLiveTranslationService?.stop()
            renpyLiveTranslationService = null
        } catch (error: Throwable) {
            Log.w(TAG, "RenPy live translation cleanup failed", error)
        }
        try {
            wineDebugCallback?.let { ProcessHelper.removeDebugCallback(it) }
            wineDebugCallback = null
        } catch (error: Throwable) {
            Log.w(TAG, "wine debug callback cleanup failed", error)
        }
        try {
            if (::runtimeBridge.isInitialized) runtimeBridge.disconnect()
        } catch (error: Throwable) {
            Log.w(TAG, "runtimeBridge cleanup failed", error)
        }
        try { launcherComponent?.stop() } catch (error: Throwable) {
            Log.w(TAG, "launcher cleanup failed", error)
        }
        try { environment?.stopEnvironmentComponents() } catch (error: Throwable) {
            Log.w(TAG, "environment cleanup failed", error)
        }
        try { winHandler?.stop() } catch (error: Throwable) {
            Log.w(TAG, "winHandler cleanup failed", error)
        }
        try { xServerView?.onPause() } catch (error: Throwable) {
            Log.w(TAG, "xServerView cleanup failed", error)
        }
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

    override fun dispatchTouchEvent(event: MotionEvent): Boolean {
        val action = event.actionMasked
        // Let UI chrome (side menu / editor) handle its own hits first.
        if (isEventOnChrome(event)) {
            return super.dispatchTouchEvent(event)
        }

        // Never block game input with the legacy full-screen blocker.
        touchBlocker?.visibility = View.GONE

        if (touchpadView == null) return super.dispatchTouchEvent(event)

        // Physical mouse → dedicated path.
        if (isMouseLike(event)) {
            val handled = touchpadView.onExternalMouseEvent(event)
            if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_HOVER_MOVE) {
                ShellLog.info(this, "Activity mouse action=$action handled=$handled")
            }
            if (handled) return true
            return super.dispatchTouchEvent(event)
        }

        // Finger touches: drive game input EXCLUSIVELY from here (single path).
        // User logs proved InputControls received DOWN but Touchpad never did when we
        // relied on nested forwarding alone — call TouchpadView directly.
        if (action == MotionEvent.ACTION_DOWN) {
            ShellLog.info(
                this,
                "Activity finger DOWN raw=${event.rawX.toInt()},${event.rawY.toInt()} " +
                    "source=${event.source} pid=${event.getPointerId(0)} " +
                    "editMode=${inputControlsView?.isEditMode}"
            )
        }

        if (inputControlsView != null && inputControlsView.isEditMode) {
            return super.dispatchTouchEvent(event)
        }

        val target: View = inputControlsView ?: touchpadView ?: return super.dispatchTouchEvent(event)
        val local = createLocalEvent(event, target)
        try {
            when (action) {
                MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN -> {
                    virtualKeyGestureActive = isOnVirtualKey(local)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    // Keep routing until after this event is delivered.
                }
            }
            val routeVirtual = virtualKeyGestureActive && inputControlsView != null
            if (routeVirtual) {
                try {
                    // Keep virtual-key path self-contained even if wiring was lost.
                    inputControlsView.setTouchpadView(touchpadView)
                    inputControlsView.setXServer(xServer)
                    inputControlsView.onTouchEvent(local)
                } catch (error: Throwable) {
                    ShellLog.error(this, "InputControls onTouchEvent crashed", error)
                }
            } else if (touchpadView != null) {
                try {
                    touchpadView.isEnabled = true
                    touchpadView.setPointerButtonLeftEnabled(true)
                    touchpadView.onTouchEvent(local)
                } catch (error: Throwable) {
                    ShellLog.error(this, "direct Touchpad onTouchEvent crashed", error)
                }
            }
            if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
                virtualKeyGestureActive = false
            }
        } finally {
            local.recycle()
        }
        return true
    }

    private fun isOnVirtualKey(local: MotionEvent): Boolean {
        val ic = inputControlsView ?: return false
        val p = ic.profile ?: return false
        if (!p.isElementsLoaded) {
            try {
                if (ic.width > 0 && ic.height > 0) p.loadElements(ic)
            } catch (_: Throwable) {}
        }
        if (!p.isElementsLoaded || p.elements.isEmpty()) return false
        val x = local.x
        val y = local.y
        return try {
            p.elements.any { it.containsPoint(x, y) }
        } catch (_: Throwable) {
            false
        }
    }

    /** Copy event with all pointers remapped into target view local space. */
    private fun createLocalEvent(event: MotionEvent, target: View): MotionEvent {
        val loc = IntArray(2)
        target.getLocationOnScreen(loc)
        val pointerCount = event.pointerCount.coerceAtLeast(1)
        val properties = Array(pointerCount) { i ->
            MotionEvent.PointerProperties().also {
                if (i < event.pointerCount) event.getPointerProperties(i, it)
                else {
                    it.id = 0
                    it.toolType = MotionEvent.TOOL_TYPE_FINGER
                }
            }
        }
        val coords = Array(pointerCount) { i ->
            MotionEvent.PointerCoords().also {
                if (i < event.pointerCount) {
                    event.getPointerCoords(i, it)
                    val rawX = if (android.os.Build.VERSION.SDK_INT >= 29) {
                        event.getRawX(i)
                    } else {
                        event.rawX + (it.x - event.x)
                    }
                    val rawY = if (android.os.Build.VERSION.SDK_INT >= 29) {
                        event.getRawY(i)
                    } else {
                        event.rawY + (it.y - event.y)
                    }
                    it.x = rawX - loc[0]
                    it.y = rawY - loc[1]
                } else {
                    it.x = event.rawX - loc[0]
                    it.y = event.rawY - loc[1]
                }
            }
        }
        return MotionEvent.obtain(
            event.downTime,
            event.eventTime,
            event.action,
            pointerCount,
            properties,
            coords,
            event.metaState,
            event.buttonState,
            event.xPrecision,
            event.yPrecision,
            event.deviceId,
            event.edgeFlags,
            event.source,
            event.flags
        )
    }

    override fun onGenericMotionEvent(event: MotionEvent): Boolean {
        if (isMouseLike(event) && touchpadView != null && !isEventOnChrome(event)) {
            if (touchpadView.onExternalMouseEvent(event)) return true
        }
        return winHandler?.onGenericMotionEvent(event) == true ||
            inputControlsView?.onGenericMotionEvent(event) == true ||
            super.onGenericMotionEvent(event)
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        return inputControlsView?.onKeyEvent(event) == true ||
            winHandler?.onKeyEvent(event) == true ||
            super.dispatchKeyEvent(event)
    }

    private fun isMouseLike(event: MotionEvent): Boolean {
        val src = event.source
        return (src and android.view.InputDevice.SOURCE_MOUSE) == android.view.InputDevice.SOURCE_MOUSE ||
            (src and android.view.InputDevice.SOURCE_MOUSE_RELATIVE) == android.view.InputDevice.SOURCE_MOUSE_RELATIVE ||
            event.getToolType(0) == MotionEvent.TOOL_TYPE_MOUSE
    }

    private fun isEventOnChrome(event: MotionEvent): Boolean {
        if (isEventOnView(toolbar, event)) return true
        if (isEventOnView(liveLogPanel, event)) return true
        if (isEventOnView(editorTopBar, event)) return true
        if (isEventOnView(editorSidePanel, event)) return true
        return false
    }

    private fun isEventOnToolbar(event: MotionEvent): Boolean = isEventOnView(toolbar, event)

    private fun isEventOnView(view: View?, event: MotionEvent): Boolean {
        if (view == null || view.visibility != View.VISIBLE || view.width <= 0 || view.height <= 0) {
            return false
        }
        val loc = IntArray(2)
        view.getLocationOnScreen(loc)
        val x = event.rawX
        val y = event.rawY
        return x >= loc[0] && x <= loc[0] + view.width && y >= loc[1] && y <= loc[1] + view.height
    }

    override fun onDestroy() {
        val containerId = runCatching { container?.id ?: -1 }.getOrDefault(-1)
        try {
            if (containerId >= 0) activeRuntimeBridges.remove(containerId)
            stopGame()
            ShellLog.info(this, "WineDisplayActivity onDestroy containerId=$containerId")
        } catch (error: Throwable) {
            ShellLog.error(this, "WineDisplayActivity onDestroy cleanup failed", error)
            Log.e(TAG, "WineDisplayActivity onDestroy cleanup failed", error)
        } finally {
            super.onDestroy()
        }
    }

    private fun showControlsEditorMenu() {
        if (inputControlsView.isEditMode) {
            // Already editing: toggle side settings for selection
            openEditorSettingsPanel()
            return
        }
        startControlsEditing()
    }

    private fun startControlsEditing() {
        inputControlsView.setShowTouchscreenControls(true)
        inputControlsView.setEditMode(true)
        inputControlsView.invalidate()
        toolbar?.setEditMode(true)
        editorUndoStack.clear()
        pushEditorUndoSnapshot()
        ensureEditorChrome()
        editorTopBar?.visibility = View.VISIBLE
        editorSidePanel?.visibility = View.GONE
        editorProfileLabel?.text = inputControlsView.profile?.name ?: "键位配置"
        editorTopBar?.bringToFront()
        toolbar?.bringToFront()
        Toast.makeText(this, "编辑模式：拖动改位置；添加后点设置改属性", Toast.LENGTH_LONG).show()
    }

    private fun finishControlsEditing() {
        hideEditorSidePanel()
        editorTopBar?.visibility = View.GONE
        saveCurrentControls()
        inputControlsView.setEditMode(false)
        toolbar?.setEditMode(false)
        editorUndoStack.clear()
        Toast.makeText(this, "键位配置已保存", Toast.LENGTH_SHORT).show()
    }

    private fun ensureEditorChrome() {
        val root = displayRoot ?: return
        if (editorTopBar == null) {
            editorTopBar = buildEditorTopBar()
            root.addView(
                editorTopBar,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.WRAP_CONTENT
                ).apply { gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL }
            )
        }
        if (editorSidePanel == null) {
            editorSidePanel = buildEditorSidePanel()
            val w = (300 * resources.displayMetrics.density).toInt()
            root.addView(
                editorSidePanel,
                FrameLayout.LayoutParams(w, FrameLayout.LayoutParams.MATCH_PARENT).apply {
                    gravity = Gravity.END
                }
            )
        }
    }

    private fun buildEditorTopBar(): View {
        val density = resources.displayMetrics.density
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding((8 * density).toInt(), (6 * density).toInt(), (8 * density).toInt(), (6 * density).toInt())
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(0xEE0F172A.toInt())
                cornerRadius = 14 * density
                setStroke((1 * density).toInt(), 0x55FFFFFF)
            }
            elevation = 8 * density
        }
        val name = TextView(this).apply {
            text = inputControlsView.profile?.name ?: "键位配置"
            setTextColor(0xFFF8FAFC.toInt())
            textSize = 12f
            maxLines = 1
            setPadding((8 * density).toInt(), 0, (10 * density).toInt(), 0)
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        editorProfileLabel = name
        bar.addView(name)
        fun chip(label: String, action: () -> Unit): TextView {
            return TextView(this).apply {
                text = label
                gravity = Gravity.CENTER
                setTextColor(0xFFE2E8F0.toInt())
                textSize = 11f
                setPadding((10 * density).toInt(), (8 * density).toInt(), (10 * density).toInt(), (8 * density).toInt())
                background = android.graphics.drawable.GradientDrawable().apply {
                    setColor(0xFF1E293B.toInt())
                    cornerRadius = 10 * density
                }
                setOnClickListener { action() }
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { marginEnd = (6 * density).toInt() }
            }
        }
        bar.addView(chip("添加") { editorAddElement() })
        bar.addView(chip("撤销") { editorUndo() })
        bar.addView(chip("删除") { editorDeleteSelected() })
        bar.addView(chip("设置") { openEditorSettingsPanel() })
        bar.addView(chip("保存") { finishControlsEditing() }.apply {
            setTextColor(0xFF0B0F16.toInt())
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(0xFF4DD6C8.toInt())
                cornerRadius = 10 * density
            }
        })
        val lpMargin = (8 * density).toInt()
        bar.setOnTouchListener { _, _ -> true } // block pass-through
        // Wrap with margins via post
        bar.post {
            val p = bar.layoutParams as? FrameLayout.LayoutParams
            p?.setMargins(lpMargin, lpMargin, lpMargin, 0)
            bar.layoutParams = p
        }
        return bar
    }

    private fun buildEditorSidePanel(): View {
        val density = resources.displayMetrics.density
        val scroll = android.widget.ScrollView(this).apply {
            visibility = View.GONE
            setBackgroundColor(0xF50B1220.toInt())
            elevation = 12 * density
            isClickable = true
        }
        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((12 * density).toInt(), (12 * density).toInt(), (12 * density).toInt(), (24 * density).toInt())
        }
        scroll.addView(col)
        scroll.tag = col
        return scroll
    }

    private fun openEditorSettingsPanel() {
        ensureEditorChrome()
        val element = inputControlsView.selectedElement
        if (element == null) {
            Toast.makeText(this, "请先点选一个键位", Toast.LENGTH_SHORT).show()
            return
        }
        val panel = editorSidePanel as? android.widget.ScrollView ?: return
        val col = panel.tag as? LinearLayout ?: return
        col.removeAllViews()
        val density = resources.displayMetrics.density
        fun title(t: String) = TextView(this).apply {
            text = t
            setTextColor(0xFF94A3B8.toInt())
            textSize = 11f
            setPadding(0, (10 * density).toInt(), 0, (4 * density).toInt())
        }
        fun head(t: String) = TextView(this).apply {
            text = t
            setTextColor(0xFFF8FAFC.toInt())
            textSize = 15f
            setPadding(0, 0, 0, (8 * density).toInt())
        }
        col.addView(head("键位设置"))
        col.addView(TextView(this).apply {
            text = describeControl(element)
            setTextColor(0xFFCBD5E1.toInt())
            textSize = 11f
            setPadding(0, 0, 0, (8 * density).toInt())
        })

        // 1 Type
        col.addView(title("1. 类型"))
        val types = listOf(
            ControlElement.Type.BUTTON to "按键",
            ControlElement.Type.D_PAD to "十字键",
            ControlElement.Type.RANGE_BUTTON to "范围按钮",
            ControlElement.Type.STICK to "摇杆",
            ControlElement.Type.TRACKPAD to "触控板"
        )
        col.addView(choiceRow(types.map { it.second }, types.indexOfFirst { it.first == element.type }.coerceAtLeast(0)) { idx ->
            pushEditorUndoSnapshot()
            element.type = types[idx].first
            saveCurrentControls()
            openEditorSettingsPanel()
        })

        // 2 Shape (buttons)
        if (element.type == ControlElement.Type.BUTTON) {
            col.addView(title("2. 形状"))
            val shapes = ControlElement.Shape.values().toList()
            col.addView(choiceRow(shapes.map(::shapeName), shapes.indexOf(element.shape).coerceAtLeast(0)) { idx ->
                pushEditorUndoSnapshot()
                element.shape = shapes[idx]
                saveCurrentControls()
                openEditorSettingsPanel()
            })
        }

        // 3 Scale 50-150
        col.addView(title("3. 缩放 ${(element.scale * 100).toInt()}%"))
        val scaleSeek = android.widget.SeekBar(this).apply {
            max = 100 // 50..150
            progress = ((element.scale * 100).toInt() - 50).coerceIn(0, 100)
        }
        val scaleLabel = TextView(this).apply {
            text = "${(element.scale * 100).toInt()}%"
            setTextColor(0xFFE2E8F0.toInt())
            gravity = Gravity.CENTER
        }
        scaleSeek.setOnSeekBarChangeListener(object : android.widget.SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: android.widget.SeekBar?, progress: Int, fromUser: Boolean) {
                scaleLabel.text = "${progress + 50}%"
            }
            override fun onStartTrackingTouch(seekBar: android.widget.SeekBar?) {
                pushEditorUndoSnapshot()
            }
            override fun onStopTrackingTouch(seekBar: android.widget.SeekBar?) {
                element.scale = ((seekBar?.progress ?: 0) + 50) / 100f
                saveCurrentControls()
            }
        })
        col.addView(scaleLabel)
        col.addView(scaleSeek)

        // 4 Binding
        col.addView(title("4. 绑定"))
        val slotCount = when (element.type) {
            ControlElement.Type.D_PAD, ControlElement.Type.STICK, ControlElement.Type.TRACKPAD -> 4
            else -> 1
        }
        for (slot in 0 until slotCount) {
            val slotLabel = if (slotCount == 4) arrayOf("上", "右", "下", "左")[slot] else "槽 ${slot + 1}"
            col.addView(actionBtn("$slotLabel：${element.getBindingAt(slot)}") {
                showBindingPicker(element, slot)
            })
        }

        // 5 Text / icon
        col.addView(title("5. 自定义文本 / 图标"))
        val textInput = EditText(this).apply {
            setText(element.text)
            hint = "显示文字，如 W / 确认"
            setTextColor(0xFFF8FAFC.toInt())
            setHintTextColor(0xFF64748B.toInt())
            setBackgroundColor(0xFF1E293B.toInt())
            setPadding((10 * density).toInt(), (8 * density).toInt(), (10 * density).toInt(), (8 * density).toInt())
        }
        col.addView(textInput)
        col.addView(actionBtn("应用文字") {
            pushEditorUndoSnapshot()
            element.text = textInput.text?.toString().orEmpty().trim()
            saveCurrentControls()
            Toast.makeText(this, "文字已更新", Toast.LENGTH_SHORT).show()
        })
        col.addView(title("预设图标（点选）"))
        val iconRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val iconScroll = android.widget.HorizontalScrollView(this).apply { addView(iconRow) }
        // 0 = none, 1..17 = assets
        for (id in 0..17) {
            val bmp = if (id == 0) null else inputControlsView.getIcon(id.toByte())
            val iv = android.widget.ImageView(this).apply {
                layoutParams = LinearLayout.LayoutParams((40 * density).toInt(), (40 * density).toInt()).apply {
                    marginEnd = (6 * density).toInt()
                }
                setBackgroundColor(if (element.iconId.toInt() == id) 0xFF334155.toInt() else 0xFF1E293B.toInt())
                setPadding((6 * density).toInt(), (6 * density).toInt(), (6 * density).toInt(), (6 * density).toInt())
                if (bmp != null) setImageBitmap(bmp)
                else setImageDrawable(null)
                contentDescription = if (id == 0) "无图标" else "图标$id"
                setOnClickListener {
                    pushEditorUndoSnapshot()
                    element.setIconId(id)
                    saveCurrentControls()
                    openEditorSettingsPanel()
                }
            }
            if (id == 0) {
                // draw a simple X via text overlay using a TextView instead
            }
            iconRow.addView(iv)
        }
        // Replace first cell with text "无"
        (iconRow.getChildAt(0) as? android.widget.ImageView)?.let { first ->
            iconRow.removeViewAt(0)
            iconRow.addView(TextView(this).apply {
                text = "无"
                gravity = Gravity.CENTER
                setTextColor(0xFFE2E8F0.toInt())
                layoutParams = LinearLayout.LayoutParams((40 * density).toInt(), (40 * density).toInt()).apply {
                    marginEnd = (6 * density).toInt()
                }
                setBackgroundColor(if (element.iconId.toInt() == 0) 0xFF334155.toInt() else 0xFF1E293B.toInt())
                setOnClickListener {
                    pushEditorUndoSnapshot()
                    element.setIconId(0)
                    saveCurrentControls()
                    openEditorSettingsPanel()
                }
            }, 0)
        }
        col.addView(iconScroll)

        col.addView(actionBtn("关闭面板") { hideEditorSidePanel() })
        panel.visibility = View.VISIBLE
        panel.bringToFront()
        editorTopBar?.bringToFront()
    }

    private fun hideEditorSidePanel() {
        editorSidePanel?.visibility = View.GONE
    }

    private fun choiceRow(labels: List<String>, selected: Int, onPick: (Int) -> Unit): View {
        val density = resources.displayMetrics.density
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        labels.forEachIndexed { idx, label ->
            wrap.addView(TextView(this).apply {
                text = if (idx == selected) "● $label" else "○ $label"
                setTextColor(if (idx == selected) 0xFF4DD6C8.toInt() else 0xFFE2E8F0.toInt())
                textSize = 13f
                setPadding((8 * density).toInt(), (8 * density).toInt(), (8 * density).toInt(), (8 * density).toInt())
                setOnClickListener { onPick(idx) }
            })
        }
        return wrap
    }

    private fun actionBtn(label: String, action: () -> Unit): TextView {
        val density = resources.displayMetrics.density
        return TextView(this).apply {
            text = label
            gravity = Gravity.CENTER
            setTextColor(0xFFF8FAFC.toInt())
            textSize = 12f
            setPadding((10 * density).toInt(), (10 * density).toInt(), (10 * density).toInt(), (10 * density).toInt())
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(0xFF1E293B.toInt())
                cornerRadius = 10 * density
            }
            val lp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            lp.topMargin = (6 * density).toInt()
            layoutParams = lp
            setOnClickListener { action() }
        }
    }

    private fun editorAddElement() {
        if (!inputControlsView.isEditMode) startControlsEditing()
        pushEditorUndoSnapshot()
        val w = inputControlsView.width.takeIf { it > 0 } ?: 1280
        val h = inputControlsView.height.takeIf { it > 0 } ?: 720
        val x = (w * 0.12f).toInt()
        val y = (h * 0.18f).toInt()
        val element = inputControlsView.addElementAt(x, y, ControlElement.Type.BUTTON)
        if (element != null) {
            element.shape = ControlElement.Shape.CIRCLE
            element.scale = 1.0f
            element.opacity = 0.75f
            element.text = "A"
            element.setBindingAt(0, Binding.KEY_A)
            saveCurrentControls()
            Toast.makeText(this, "已在左上角添加圆形按键，可拖动；点设置改属性", Toast.LENGTH_LONG).show()
        }
    }

    private fun editorDeleteSelected() {
        val element = inputControlsView.selectedElement
        if (element == null) {
            Toast.makeText(this, "请先点选要删除的键位", Toast.LENGTH_SHORT).show()
            return
        }
        pushEditorUndoSnapshot()
        inputControlsView.removeElement()
        saveCurrentControls()
        hideEditorSidePanel()
    }

    private fun editorUndo() {
        if (editorUndoStack.isEmpty()) {
            Toast.makeText(this, "没有可撤销的操作", Toast.LENGTH_SHORT).show()
            return
        }
        val snapshot = editorUndoStack.removeAt(editorUndoStack.lastIndex)
        restoreEditorSnapshot(snapshot)
        hideEditorSidePanel()
        Toast.makeText(this, "已撤销", Toast.LENGTH_SHORT).show()
    }

    private fun pushEditorUndoSnapshot() {
        val profile = inputControlsView.profile ?: return
        if (!profile.isElementsLoaded) profile.loadElements(inputControlsView)
        try {
            val arr = org.json.JSONArray()
            for (el in profile.elements) {
                val obj = el.toJSONObject() ?: continue
                arr.put(obj)
            }
            val json = arr.toString()
            if (editorUndoStack.lastOrNull() == json) return
            editorUndoStack.add(json)
            while (editorUndoStack.size > 20) editorUndoStack.removeAt(0)
        } catch (_: Throwable) {}
    }

    private fun restoreEditorSnapshot(json: String) {
        val profile = inputControlsView.profile ?: return
        try {
            val arr = org.json.JSONArray(json)
            val existing = profile.elements.toList()
            for (el in existing) profile.removeElement(el)
            val maxW = inputControlsView.maxWidth.takeIf { it > 0 }
                ?: inputControlsView.width.coerceAtLeast(1)
            val maxH = inputControlsView.maxHeight.takeIf { it > 0 }
                ?: inputControlsView.height.coerceAtLeast(1)
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                val el = ControlElement(inputControlsView)
                el.type = ControlElement.Type.valueOf(obj.getString("type"))
                el.shape = ControlElement.Shape.valueOf(obj.getString("shape"))
                el.isToggleSwitch = obj.optBoolean("toggleSwitch", false)
                el.setX((obj.getDouble("x") * maxW).toInt())
                el.setY((obj.getDouble("y") * maxH).toInt())
                el.scale = obj.getDouble("scale").toFloat()
                el.text = obj.optString("text")
                el.setIconId(obj.optInt("iconId", 0))
                if (obj.has("opacity")) el.opacity = obj.getDouble("opacity").toFloat()
                val bindings = obj.optJSONArray("bindings")
                if (bindings != null) {
                    for (j in 0 until bindings.length()) {
                        el.setBindingAt(j, Binding.fromString(bindings.getString(j)))
                    }
                }
                profile.addElement(el)
            }
            profile.save()
            inputControlsView.invalidate()
        } catch (error: Throwable) {
            Log.w(TAG, "restoreEditorSnapshot failed", error)
        }
    }

    private fun saveCurrentControls() {
        inputControlsView.profile?.save()
        inputControlsView.invalidate()
    }

    private fun selectedOrToast(): ControlElement? {
        return inputControlsView.selectedElement ?: run {
            Toast.makeText(this, "请先点击并选中一个虚拟键位。", Toast.LENGTH_SHORT).show()
            null
        }
    }

    private fun describeControl(element: ControlElement): String {
        val bindings = (0 until element.bindingCount.toInt())
            .map { element.getBindingAt(it).toString() }
            .joinToString(" / ")
        val label = element.text.ifBlank { "自动显示按键名" }
        return "${controlTypeName(element.type)} · ${shapeName(element.shape)}\n" +
            "大小 ${(element.scale * 100).toInt()}% · $label\n$bindings"
    }

    private fun showBindingPicker(element: ControlElement, slot: Int) {
        val values = (
            Binding.keyboardBindingValues().asList() +
                Binding.mouseBindingValues().asList() +
                Binding.gamepadBindingValues().asList()
            ).distinct()
        val labels = values.map { it.toString() }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle("设置绑定")
            .setSingleChoiceItems(labels, values.indexOf(element.getBindingAt(slot)).coerceAtLeast(0)) { dialog, which ->
                pushEditorUndoSnapshot()
                val binding = values[which]
                element.setBindingAt(slot, binding)
                if (element.type == ControlElement.Type.BUTTON && slot == 0 && element.text.isBlank()) {
                    element.text = binding.toString()
                }
                saveCurrentControls()
                dialog.dismiss()
                openEditorSettingsPanel()
            }
            .setNegativeButton("取消", null)
            .show()
    }

    private fun controlTypeName(type: ControlElement.Type): String = when (type) {
        ControlElement.Type.BUTTON -> "按键"
        ControlElement.Type.D_PAD -> "十字键"
        ControlElement.Type.RANGE_BUTTON -> "范围按钮"
        ControlElement.Type.STICK -> "摇杆"
        ControlElement.Type.TRACKPAD -> "触控板"
        ControlElement.Type.MIDI_KEY -> "MIDI 键"
        ControlElement.Type.RADIAL_MENU -> "环形菜单"
    }

    private fun shapeName(shape: ControlElement.Shape): String = when (shape) {
        ControlElement.Shape.CIRCLE -> "圆形"
        ControlElement.Shape.RECT -> "矩形"
        ControlElement.Shape.ROUND_RECT -> "圆角矩形"
        ControlElement.Shape.SQUARE -> "正方形"
    }

    companion object {
        const val EXTRA_GAME_TREE_URI = "game_tree_uri"
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

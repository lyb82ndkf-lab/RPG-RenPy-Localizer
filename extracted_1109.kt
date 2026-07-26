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
{"step_index":11,"source":"MODEL","type":"VIEW_FILE","status":"DONE","created_at":"2026-07-24T07:34:14Z","content":"Created At: 2026-07-24T15:34:14+08:00\nCompleted At: 2026-07-24T15:34:14+08:00\nFile Path: `file:///d:/%E7%A8%8B%E5%BA%8F/RPG%20tool/android_app/shell/app/src/main/java/com/rpgrtl/shell/wine/WineDisplayActivity.kt`\nTotal Lines: 1109\nTotal Bytes: 49233\nShowing lines 1 to 800\nThe following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.\n1: package com.rpgrtl.shell.wine\r\n2: \r\n3: import android.app.AlertDialog\r\n4: import android.os.Bundle\r\n5: import android.os.Build\r\n6: import android.os.Handler\r\n7: import android.os.Looper\r\n8: import android.content.Intent\r\n9: import android.content.pm.ActivityInfo\r\n10: import android.content.res.Configuration\r\n11: import android.net.Uri\r\n12: import android.util.Log\r\n13: import android.view.Gravity\r\n14: import android.view.KeyEvent\r\n15: import android.view.MotionEvent\r\n16: import android.view.View\r\n17: import android.view.WindowManager\r\n18: import android.widget.FrameLayout\r\n19: import android.widget.Toast\r\n20: import com.rpgrtl.engine.XServerDisplayActivity\r\n21: import com.rpgrtl.engine.box64.Box64Preset\r\n22: import com.rpgrtl.engine.container.Container\r\n23: import com.rpgrtl.engine.container.ContainerManager\r\n24: import com.rpgrtl.engine.container.GraphicsDrivers\r\n25: import com.rpgrtl.engine.alsaserver.ALSAClient\r\n26: import com.rpgrtl.engine.container.DXWrappers\r\n27: import com.rpgrtl.engine.core.AppUtils\r\n28: import com.rpgrtl.engine.core.DefaultVersion\r\n29: import com.rpgrtl.engine.core.EnvVars\r\n30: import com.rpgrtl.engine.core.FileUtils\r\n31: import com.rpgrtl.engine.core.GeneralComponents\r\n32: import com.rpgrtl.engine.core.TarCompressorUtils\r\n33: import com.rpgrtl.engine.core.GPUHelper\r\n34: import com.rpgrtl.engine.core.WineInfo\r\n35: import com.rpgrtl.engine.core.WineUtils\r\n36: import com.rpgrtl.engine.widget.InputControlsView\r\n37: import com.rpgrtl.engine.inputcontrols.InputControlsManager\r\n38: import com.rpgrtl.engine.widget.TouchpadView\r\n39: import com.rpgrtl.engine.widget.XServerView\r\n40: import com.rpgrtl.engine.winhandler.WinHandler\r\n41: import com.rpgrtl.engine.xconnector.UnixSocketConfig\r\n42: import com.rpgrtl.engine.xenvironment.RootFS\r\n43: import com.rpgrtl.engine.xenvironment.RootFSInstaller\r\n44: import com.rpgrtl.engine.xenvironment.XEnvironment\r\n45: import com.rpgrtl.engine.xenvironment.components.ALSAServerComponent\r\n46: import com.rpgrtl.engine.xenvironment.components.GuestProgramLauncherComponent\r\n47: import com.rpgrtl.engine.xenvironment.components.SysVSharedMemoryComponent\r\n48: import com.rpgrtl.engine.xenvironment.components.VirGLRendererComponent\r\n49: import com.rpgrtl.engine.xenvironment.components.XServerComponent\r\n50: import com.rpgrtl.engine.xserver.ScreenInfo\r\n51: import com.rpgrtl.engine.xserver.XServer\r\n52: import com.rpgrtl.shell.MainActivity\r\n53: import com.rpgrtl.shell.ShellLog\r\n54: import androidx.preference.PreferenceManager\r\n55: import java.io.File\r\n56: import java.util.Locale\r\n57: import java.util.concurrent.ConcurrentHashMap\r\n58: \r\n59: class WineDisplayActivity : XServerDisplayActivity(), FloatingToolbar.Listener {\r\n60:     private var launcherComponent: GuestProgramLauncherComponent? = null\r\n61:     private lateinit var runtimeBridge: RuntimeBridge\r\n62:     private var toolbar: FloatingToolbar? = null\r\n63:     private var touchBlocker: View? = null\r\n64:     private var touchBlocked = false\r\n65:     private var gameExePath = \"\"\r\n66:     private var gameWorkDir = \"\"\r\n67:     private var selectedBox64Preset = Box64Preset.PERFORMANCE\r\n68:     private var selectedGraphicsDriver = \"\"\r\n69: \r\n70:     override fun onCreate(savedInstanceState: Bundle?) {\r\n71:         super.onCreate(savedInstanceState)\r\n72:         ShellLog.installCrashLogger(this)\r\n73:         ShellLog.info(this, \"WineDisplayActivity onCreate\")\r\n74:         AppUtils.hideSystemUI(this)\r\n75:         AppUtils.keepScreenOn(this)\r\n76:         window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)\r\n77:         requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE\r\n78: \r\n79:         val rawExePath = intent.getStringExtra(EXTRA_GAME_URI).orEmpty()\r\n80:         val gameTreeUri = intent.getStringExtra(EXTRA_GAME_TREE_URI).orEmpty()\r\n81:         val gameTitle = intent.getStringExtra(EXTRA_GAME_TITLE).orEmpty().ifBlank { \"Windows Game\" }\r\n82:         val containerId = intent.getIntExtra(EXTRA_CONTAINER_ID, 0)\r\n83:         runtimeBridge = RuntimeBridge(containerId.toString())\r\n84:         ShellLog.info(\r\n85:             this,\r\n86:             \"Wine launch requested title=$gameTitle containerId=$containerId uri=$rawExePath tree=$gameTreeUri\"\r\n87:         )\r\n88: \r\n89:         if (rawExePath.isBlank()) {\r\n90:             ShellLog.error(this, \"Wine launch failed: blank exe path\")\r\n91:             Toast.makeText(this, \"未找到可启动的 exe 路径。\", Toast.LENGTH_LONG).show()\r\n92:             finish()\r\n93:             return\r\n94:         }\r\n95: \r\n96:         rootFS = RootFS.find(this)\r\n97:         if (!rootFS.isValid && !installBundledWineRuntime()) {\r\n98:             ShellLog.error(this, \"Wine launch failed: bundled runtime initialization failed\")\r\n99:             Toast.makeText(this, \"内置 Winlator 运行环境初始化失败，无法启动 Ren'Py / Windows 游戏。\", Toast.LENGTH_LONG).show()\r\n100:             finish()\r\n101:             return\r\n102:         }\r\n103: \r\n104:         if (!prepareContainer(containerId, gameTitle)) return\r\n105: \r\n106:         // Show a black landscape surface immediately while files prepare (can take long on SAF copy).\r\n107:         val loading = FrameLayout(this).apply {\r\n108:             setBackgroundColor(0xFF000000.toInt())\r\n109:             systemUiVisibility = immersiveFlags()\r\n110:         }\r\n111:         setContentView(loading)\r\n112:         Toast.makeText(this, \"正在准备游戏文件并启动 Wine：$gameTitle\", Toast.LENGTH_LONG).show()\r\n113: \r\n114:         Thread {\r\n115:             try {\r\n116:                 val prepared = prepareGameFiles(rawExePath, gameTreeUri, gameTitle)\r\n117:                 gameExePath = prepared.exePath\r\n118:                 gameWorkDir = prepared.workDir\r\n119:                 ShellLog.info(this, \"Wine executable prepared path=$gameExePath workDir=$gameWorkDir\")\r\n120:                 // Heavy extract + gladio path patch on worker thread (not UI).\r\n121:                 prepareWineRuntime()\r\n122:                 runOnUiThread {\r\n123:                     if (isFinishing) return@runOnUiThread\r\n124:                     startWineDisplay(gameTitle)\r\n125:                 }\r\n126:             } catch (error: Throwable) {\r\n127:                 ShellLog.error(this, \"Wine launch failed while preparing game files\", error)\r\n128:                 runOnUiThread {\r\n129:                     Toast.makeText(this, \"准备游戏文件失败: ${error.message}\", Toast.LENGTH_LONG).show()\r\n130:                     finish()\r\n131:                 }\r\n132:             }\r\n133:         }.start()\r\n134:     }\r\n135: \r\n136:     private fun startWineDisplay(gameTitle: String) {\r\n137:         // Match physical display orientation so landscape phones get a landscape X desktop.\r\n138:         val dm = resources.displayMetrics\r\n139:         val screenW = maxOf(dm.widthPixels, dm.heightPixels).coerceAtLeast(1280)\r\n140:         val screenH = minOf(dm.widthPixels, dm.heightPixels).coerceAtLeast(720)\r\n141:         val dynamicScreen = \"${screenW}x${screenH}\"\r\n142:         container.setScreenSize(dynamicScreen)\r\n143:         screenInfo = ScreenInfo(dynamicScreen)\r\n144:         ShellLog.info(this, \"Wine display init screen=$dynamicScreen device=${dm.widthPixels}x${dm.heightPixels}\")\r\n145:         xServer = XServer(this, screenInfo)\r\n146:         winHandler = WinHandler(this)\r\n147:         xServer.setWinHandler(winHandler)\r\n148: \r\n149:         ShellLog.info(this, \"Creating XServerView / renderer\")\r\n150:         xServerView = XServerView(this, xServer)\r\n151:         xServer.setRenderer(xServerView.renderer)\r\n152: \r\n153:         touchpadView = TouchpadView(this, xServer, false)\r\n154:         val tp = touchpadView\r\n155:         val xs = xServer\r\n156:         inputControlsView = InputControlsView(this).apply {\r\n157:             setXServer(xs)\r\n158:             setTouchpadView(tp)\r\n159:             setShowTouchscreenControls(true)\r\n160:         }\r\n161: \r\n162:         environment = XEnvironment(this, rootFS)\r\n163:         addRuntimeComponents()\r\n164:         setContentView(createDisplayLayout(gameTitle))\r\n165: \r\n166:         // Defer profile loading until after layout so view has valid dimensions;\r\n167:         // loadElements() converts ratio-based positions to pixels using getWidth()/getHeight()\r\n168:         inputControlsView.post {\r\n169:             loadDefaultControlsProfile(inputControlsView)\r\n170:             inputControlsView.invalidate()\r\n171:         }\r\n172: \r\n173:         winHandler.start()\r\n174:         ShellLog.info(this, \"Starting Wine environment components\")\r\n175:         environment.startEnvironmentComponents()\r\n176:         activeRuntimeBridges[container.id] = runtimeBridge\r\n177:         // Verify X11 socket appeared under rootfs (host server).\r\n178:         val x11 = File(rootFS.rootDir, \"tmp/.X11-unix/X0\")\r\n179:         ShellLog.info(this, \"X11 socket path=${x11.absolutePath} exists=${x11.exists()}\")\r\n180:         // Short delay so XServer/ALSA bind before wine attaches to DISPLAY=:0.\r\n181:         Handler(Looper.getMainLooper()).postDelayed({\r\n182:             val box64 = File(rootFS.rootDir, \"usr/local/bin/box64\")\r\n183:             val wineBin = File(rootFS.rootDir, \"opt/wine/bin/wine\")\r\n184:             val ntdll = File(rootFS.rootDir, \"opt/wine/lib/wine/x86_64-unix/ntdll.so\")\r\n185:             val ntdllPatched = ntdll.isFile && !WinePathCompat.containsAscii(ntdll, \"com.winlator\")\r\n186:             val box64Patched = box64.isFile && !WinePathCompat.containsAscii(box64, \"com.winlator\")\r\n187:             ShellLog.info(\r\n188:                 this,\r\n189:                 \"Starting Wine guest launcher path=$gameExePath workDir=$gameWorkDir \" +\r\n190:                     \"x11Exists=${x11.exists()} bridgeX11=${WinePathCompat.newX11Path(this)} \" +\r\n191:                     \"bridgeX11Exists=${File(WinePathCompat.newX11Path(this)).exists()} \" +\r\n192:                     \"box64Exists=${box64.isFile} box64Size=${box64.length()} box64Patched=$box64Patched \" +\r\n193:                     \"wineExists=${wineBin.isFile} ntdllPatched=$ntdllPatched \" +\r\n194:                     \"cmd=${launcherComponent?.guestExecutable}\"\r\n195:             )\r\n196:             try {\r\n197:                 // Final safety: re-patch box64 INTERP right before exec.\r\n198:                 val box64Ready = WinePathCompat.patchBox64Interpreter(this)\r\n199:                 if (!box64Ready) {\r\n200:                     ShellLog.error(this, \"Abort launch: box64 INTERP not patched\")\r\n201:                     Toast.makeText(this, \"box64 解释器路径未修复，无法启动 Wine\", Toast.LENGTH_LONG).show()\r\n202:                     return@postDelayed\r\n203:                 }\r\n204:                 launcherComponent?.start()\r\n205:                 val pid = launcherComponent?.getPid() ?: -1\r\n206:                 ShellLog.info(this, \"launcherComponent.start() returned pid=$pid\")\r\n207:                 if (pid <= 0) {\r\n208:                     Toast.makeText(this, \"Wine 进程启动失败 (pid=$pid)，请查看运行日志。\", Toast.LENGTH_LONG).show()\r\n209:                 }\r\n210:             } catch (error: Throwable) {\r\n211:                 ShellLog.error(this, \"launcherComponent.start() failed\", error)\r\n212:             }\r\n213:         }, 900)\r\n214: \r\n215:         Toast.makeText(this, \"容器已就绪，正在启动：$gameTitle\", Toast.LENGTH_SHORT).show()\r\n216:     }\r\n217: \r\n218:     private fun installBundledWineRuntime(): Boolean {\r\n219:         return try {\r\n220:             ShellLog.info(this, \"Installing bundled Winlator runtime\")\r\n221:             Toast.makeText(this, \"正在初始化内置 Winlator 运行环境...\", Toast.LENGTH_LONG).show()\r\n222:             val rootDir = rootFS.rootDir\r\n223:             FileUtils.delete(rootDir)\r\n224:             rootDir.mkdirs()\r\n225:             val ok = TarCompressorUtils.extract(TarCompressorUtils.Type.ZSTD, this, \"winlator/rootfs.tzst\", rootDir)\r\n226:             if (ok) rootFS.createRFSVersionFile(RootFSInstaller.LATEST_VERSION.toInt())\r\n227:             ok && rootFS.isValid\r\n228:         } catch (error: Throwable) {\r\n229:             Log.e(TAG, \"Bundled Wine runtime install failed\", error)\r\n230:             ShellLog.error(this, \"Bundled Wine runtime install failed\", error)\r\n231:             false\r\n232:         }\r\n233:     }\r\n234: \r\n235:     private fun prepareContainer(containerId: Int, gameTitle: String): Boolean {\r\n236:         val manager = ContainerManager(this)\r\n237:         container = if (containerId > 0) {\r\n238:             manager.getContainerById(containerId)\r\n239:         } else {\r\n240:             manager.containers.firstOrNull() ?: manager.ensureDefaultContainer(gameTitle)\r\n241:         }\r\n242: \r\n243:         if (container == null) {\r\n244:             ShellLog.error(this, \"Wine launch failed: container initialization failed\")\r\n245:             Toast.makeText(this, \"内置 Winlator 容器初始化失败。\", Toast.LENGTH_LONG).show()\r\n246:             finish()\r\n247:             return false\r\n248:         }\r\n249: \r\n250:         if (container.name.isNullOrBlank() || container.name.startsWith(\"Container-\")) {\r\n251:             container.setName(gameTitle)\r\n252:         }\r\n253:         selectedBox64Preset = resolveBox64Preset()\r\n254:         selectedGraphicsDriver = resolveGraphicsDriver()\r\n255:         container.setBox64Preset(selectedBox64Preset)\r\n256:         container.setGraphicsDriver(selectedGraphicsDriver)\r\n257:         // Ren'Py uses SDL2 OpenGL — WineD3D is safer than DXVK for pure GL titles.\r\n258:         container.setDXWrapper(DXWrappers.WINED3D)\r\n259:         container.setStartupSelection(Container.STARTUP_SELECTION_ESSENTIAL)\r\n260:         Log.i(TAG, \"Wine launch profile: box64=$selectedBox64Preset graphics=$selectedGraphicsDriver\")\r\n261:         ShellLog.info(this, \"Wine launch profile: box64=$selectedBox64Preset graphics=$selectedGraphicsDriver\")\r\n262:         manager.activateContainer(container)\r\n263:         return true\r\n264:     }\r\n265: \r\n266:     /**\r\n267:      * Full Winlator-style prep: extract guest GPU drivers once, patch gladio package paths,\r\n268:      * wineprefix tweaks. Second launch skips heavy extract (marker file).\r\n269:      */\r\n270:     private fun prepareWineRuntime() {\r\n271:         val rootDir = rootFS.rootDir\r\n272:         val marker = File(rootDir, \".winlator/rpgtl_runtime_prepared_v2\")\r\n273:         val drivers = GraphicsDrivers.parseIdentifiers(selectedGraphicsDriver)\r\n274:         val vulkan = drivers[0]\r\n275:         val opengl = drivers[1]\r\n276:         val hasGladio = File(rootDir, \"usr/lib/libGL.so.1.7.0\").isFile ||\r\n277:             File(rootDir, \"usr/lib/libGL.so.1\").isFile ||\r\n278:             File(rootDir, \"usr/lib/libGL.so\").isFile\r\n279:         val alreadyPrepared = marker.isFile && hasGladio\r\n280: \r\n281:         ShellLog.info(\r\n282:             this,\r\n283:             \"Preparing Wine runtime drivers vulkan=$vulkan opengl=$opengl prepared=$alreadyPrepared\"\r\n284:         )\r\n285: \r\n286:         // Always ensure path bridge (cheap symlink) before any guest call.\r\n287:         WinePathCompat.ensureBridge(this)\r\n288: \r\n289:         if (!alreadyPrepared) {\r\n290:             runOnUiThread {\r\n291:                 Toast.makeText(this, \"首次初始化 Wine 环境（仅一次，请稍候）...\", Toast.LENGTH_LONG).show()\r\n292:             }\r\n293: \r\n294:             runCatching {\r\n295:                 TarCompressorUtils.extract(\r\n296:                     TarCompressorUtils.Type.ZSTD,\r\n297:                     this,\r\n298:                     \"winlator/rootfs_patches.tzst\",\r\n299:                     rootDir\r\n300:                 )\r\n301:             }\r\n302: \r\n303:             try {\r\n304:                 GeneralComponents.extractFile(\r\n305:                     GeneralComponents.Type.BOX64,\r\n306:                     this,\r\n307:                     DefaultVersion.BOX64,\r\n308:                     DefaultVersion.BOX64\r\n309:                 )\r\n310:                 val box64 = File(rootDir, \"usr/local/bin/box64\")\r\n311:                 FileUtils.chmod(box64, 0b111_101_101) // 0755\r\n312:                 // Mark version so GuestProgramLauncher won't re-extract and wipe INTERP patch.\r\n313:                 PreferenceManager.getDefaultSharedPreferences(this)\r\n314:                     .edit()\r\n315:                     .putString(\"current_box64_version\", DefaultVersion.BOX64)\r\n316:                     .putString(\"box64_version\", DefaultVersion.BOX64)\r\n317:                     .apply()\r\n318:                 ShellLog.info(this, \"Box64 extract done exists=${box64.isFile} size=${box64.length()}\")\r\n319:                 WinePathCompat.patchBox64Interpreter(this)\r\n320:             } catch (error: Throwable) {\r\n321:                 ShellLog.error(this, \"Box64 extract failed\", error)\r\n322:             }\r\n323: \r\n324:             extractDriverOnce(opengl, when (opengl) {\r\n325:                 GraphicsDrivers.VIRGL -> DefaultVersion.VIRGL\r\n326:                 GraphicsDrivers.ZINK -> DefaultVersion.ZINK\r\n327:                 else -> DefaultVersion.GLADIO\r\n328:             })\r\n329:             if (opengl != GraphicsDrivers.GLADIO) {\r\n330:                 extractDriverOnce(GraphicsDrivers.GLADIO, DefaultVersion.GLADIO)\r\n331:             }\r\n332: \r\n333:             extractDriverOnce(vulkan, when (vulkan) {\r\n334:                 GraphicsDrivers.TURNIP -> DefaultVersion.TURNIP\r\n335:                 GraphicsDrivers.VORTEK -> DefaultVersion.VORTEK\r\n336:                 else -> DefaultVersion.TURNIP\r\n337:             })\r\n338: \r\n339:             try {\r\n340:                 GeneralComponents.extractFile(\r\n341:                     GeneralComponents.Type.DXVK,\r\n342:                     this,\r\n343:                     DefaultVersion.DXVK(vulkan),\r\n344:                     DefaultVersion.MAJOR_DXVK\r\n345:                 )\r\n346:                 ShellLog.info(this, \"DXVK extract done\")\r\n347:             } catch (error: Throwable) {\r\n348:                 ShellLog.error(this, \"DXVK extract failed\", error)\r\n349:             }\r\n350: \r\n351:             try {\r\n352:                 extractDefaultWinComponents()\r\n353:             } catch (error: Throwable) {\r\n354:                 ShellLog.error(this, \"Wincomponents extract failed\", error)\r\n355:             }\r\n356: \r\n357:             try {\r\n358:                 WineUtils.applySystemTweaks(this, WineInfo.MAIN_WINE_INFO)\r\n359:                 WineUtils.changeServicesStatus(container, true)\r\n360:                 ShellLog.info(this, \"Wineprefix system tweaks applied\")\r\n361:             } catch (error: Throwable) {\r\n362:                 ShellLog.error(this, \"Wineprefix tweaks failed\", error)\r\n363:             }\r\n364: \r\n365:             marker.parentFile?.mkdirs()\r\n366:             FileUtils.writeString(marker, System.currentTimeMillis().toString())\r\n367:             ShellLog.info(this, \"Runtime marker written ${marker.absolutePath}\")\r\n368:         } else {\r\n369:             ShellLog.info(this, \"Skipping heavy extract (container already prepared)\")\r\n370:             runCatching {\r\n371:                 GeneralComponents.extractFile(\r\n372:                     GeneralComponents.Type.BOX64,\r\n373:                     this,\r\n374:                     DefaultVersion.BOX64,\r\n375:                     DefaultVersion.BOX64\r\n376:                 )\r\n377:                 FileUtils.chmod(File(rootDir, \"usr/local/bin/box64\"), 0b111_101_101)\r\n378:                 WinePathCompat.patchBox64Interpreter(this)\r\n379:             }\r\n380:         }\r\n381: \r\n382:         // Patch only the files that are known to carry Winlator's package-root paths.\n383:         // A full rootfs walk is too expensive on phones and can look like a dead launch.\n384:         ShellLog.info(this, \"Runtime path patch: core files start\")\n385:         val replaced = WinePathCompat.patchCoreRuntimePaths(this)\n386:         ShellLog.info(this, \"Runtime path patch: box64 start\")\n387:         val box64Ok = WinePathCompat.patchBox64Interpreter(this)\n388:         ShellLog.info(this, \"Runtime path patch: gladio start\")\n389:         val gladioOk = WinePathCompat.patchGuestGladio(this)\n390:         ShellLog.info(\n391:             this,\n392:             \"Rootfs core path rewrite replacements=$replaced box64Ok=$box64Ok gladioOk=$gladioOk \" +\n393:                 \"newPrefix=${WinePathCompat.newRootfsPrefix(this)}\"\n394:         )\n395:         if (!box64Ok) {\r\n396:             ShellLog.error(this, \"box64 still contains com.winlator INTERP — guest will not start\")\r\n397:         }\r\n398:     }\r\n399: \r\n400:     private fun extractDriverOnce(name: String, version: String) {\r\n401:         val ok = GeneralComponents.extractGraphicsDriverAsset(this, name, version)\r\n402:         ShellLog.info(this, \"Graphics driver extract $name-$version ok=$ok\")\r\n403:     }\r\n404: \r\n405:     private fun extractDefaultWinComponents() {\r\n406:         // Extract into the active container wineprefix (not the shared home/xuser tree only).\r\n407:         val needed = listOf(\"directsound\", \"xaudio\", \"vcrun2010\")\r\n408:         val dest = File(container.getRootDir(), \".wine/drive_c/windows\")\r\n409:         dest.mkdirs()\r\n410:         for (id in needed) {\r\n411:             val asset = \"winlator/wincomponents/$id.tzst\"\r\n412:             val ok = TarCompressorUtils.extract(TarCompressorUtils.Type.ZSTD, this, asset, dest)\r\n413:             ShellLog.info(this, \"Wincomponent $id extract ok=$ok dest=${dest.absolutePath}\")\r\n414:         }\r\n415:         try {\r\n416:             WineUtils.overrideWinComponentDlls(this, container, container.getWinComponents())\r\n417:         } catch (error: Throwable) {\r\n418:             ShellLog.error(this, \"overrideWinComponentDlls failed\", error)\r\n419:         }\r\n420:     }\r\n421: \r\n422:     private fun loadDefaultControlsProfile(view: InputControlsView) {\r\n423:         val manager = InputControlsManager(this)\r\n424:         val profile = manager.getProfiles(true).firstOrNull()\r\n425:         if (profile != null) {\r\n426:             profile.loadElements(view)\r\n427:             view.setProfile(profile)\r\n428:             Log.i(TAG, \"Loaded touchscreen controls profile: ${profile.name} (${profile.elements.size} elements)\")\r\n429:         } else {\r\n430:             Log.w(TAG, \"No touchscreen controls profile found; virtual controls will be empty.\")\r\n431:         }\r\n432:     }\r\n433: \r\n434:     private fun addRuntimeComponents() {\r\n435:         WinePathCompat.ensureBridge(this)\r\n436: \r\n437:         val rootDir = rootFS.rootDir\r\n438:         // Prefer short bridge path for sockets so guest libs (patched to .../files/w) match.\r\n439:         val bridgeRoot = WinePathCompat.shortRootfsLink(this).let {\r\n440:             if (it.exists()) it.absolutePath else rootDir.absolutePath\r\n441:         }\r\n442:         val drivers = GraphicsDrivers.parseIdentifiers(selectedGraphicsDriver)\r\n443:         val vulkan = drivers[0]\r\n444:         val opengl = drivers[1]\r\n445: \r\n446:         File(rootDir, \"tmp/.X11-unix\").mkdirs()\r\n447:         File(rootDir, \"tmp/.sound\").mkdirs()\r\n448:         File(rootDir, \"tmp/.sysvshm\").mkdirs()\r\n449:         File(rootDir, \"tmp/shm\").mkdirs()\r\n450: \r\n451:         // Host X server listens on real rootfs path; bridge symlink makes .../w/tmp/... the same inode.\r\n452:         environment.addComponent(\r\n453:             XServerComponent(\r\n454:                 xServer,\r\n455:                 UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.XSERVER_PATH)\r\n456:             )\r\n457:         )\r\n458:         environment.addComponent(\r\n459:             SysVSharedMemoryComponent(\r\n460:                 xServer,\r\n461:                 UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.SYSVSHM_SERVER_PATH)\r\n462:             )\r\n463:         )\r\n464: \r\n465:         if (opengl == GraphicsDrivers.VIRGL) {\r\n466:             environment.addComponent(\r\n467:                 VirGLRendererComponent(\r\n468:                     xServer,\r\n469:                     UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.VIRGL_SERVER_PATH)\r\n470:                 )\r\n471:             )\r\n472:             ShellLog.info(this, \"VirGLRendererComponent added\")\r\n473:         }\r\n474: \r\n475:         environment.addComponent(\r\n476:             ALSAServerComponent(\r\n477:                 UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.ALSA_SERVER_PATH),\r\n478:                 ALSAClient.Options()\r\n479:             )\r\n480:         )\r\n481: \r\n482:         val winePrefix = File(container.getRootDir(), \".wine\").absolutePath\r\n483:         // Guest-facing paths must use the SHORT bridge prefix (what we patched into .so files).\r\n484:         val guestRoot = WinePathCompat.newRootfsPrefix(this)\r\n485:         val alsaSocket = \"$guestRoot${UnixSocketConfig.ALSA_SERVER_PATH}\"\r\n486:         val sysvSocket = \"$guestRoot${UnixSocketConfig.SYSVSHM_SERVER_PATH}\"\r\n487:         val tmpDir = \"$guestRoot/tmp\"\r\n488:         val env = EnvVars(container.envVars)\r\n489:         env.put(\"WINEPREFIX\", winePrefix)\r\n490:         env.put(\"HOME\", rootDir.absolutePath + RootFS.HOME_PATH)\r\n491:         // Critical: Xlib builds /tmp/.X11-unix from TMPDIR on some builds; always set both.\r\n492:         env.put(\"TMPDIR\", tmpDir)\r\n493:         env.put(\"TEMP\", tmpDir)\r\n494:         env.put(\"TMP\", tmpDir)\r\n495:         env.put(\"DISPLAY\", \":0\")\r\n496:         env.put(\"WINEDLLOVERRIDES\", \"winemenubuilder.exe=d;mscoree,mshtml=\")\r\n497:         env.put(\"ANDROID_ALSA_SERVER\", alsaSocket)\r\n498:         env.put(\"ANDROID_SYSVSHM_SERVER\", sysvSocket)\r\n499:         env.put(\"ALSA_PLUGIN_DIR\", \"$guestRoot/usr/lib/alsa-lib\")\r\n500:         env.put(\"SDL_AUDIODRIVER\", \"alsa\")\r\n501:         env.put(\"PULSE_SERVER\", \"\")\r\n502:         env.put(\"BOX64_LOG\", \"1\")\r\n503:         env.put(\"BOX64_NOBANNER\", \"0\")\r\n504:         env.put(\"WINEDEBUG\", \"-all,+err,+fix\")\r\n505:         env.put(\"NWJS_ARGS\", \"--remote-debugging-port=${RuntimeBridge.CDP_PORT}\")\r\n506:         env.put(\"CHROME_REMOTE_DEBUGGING_PORT\", RuntimeBridge.CDP_PORT.toString())\r\n507:         if (gameWorkDir.isNotBlank()) {\r\n508:             env.put(\"WINEPATH\", gameWorkDir)\r\n509:         }\r\n510:         applyPerformanceEnv(env, selectedGraphicsDriver)\r\n511:         ShellLog.info(\r\n512:             this,\r\n513:             \"Runtime env ready vulkan=$vulkan opengl=$opengl winePrefix=$winePrefix \" +\r\n514:                 \"guestRoot=$guestRoot alsa=$alsaSocket tmp=$tmpDir x11=${WinePathCompat.newX11Path(this)} \" +\r\n515:                 \"bridgeRoot=$bridgeRoot\"\r\n516:         )\r\n517: \r\n518:         com.rpgrtl.engine.core.ProcessHelper.removeAllDebugCallbacks()\r\n519:         com.rpgrtl.engine.core.ProcessHelper.addDebugCallback { line ->\r\n520:             if (line.isNullOrBlank()) return@addDebugCallback\r\n521:             val text = line.trim()\r\n522:             if (text.isEmpty()) return@addDebugCallback\r\n523:             ShellLog.info(this@WineDisplayActivity, \"WINE: $text\")\r\n524:             Log.i(TAG, \"WINE: $text\")\r\n525:         }\r\n526: \r\n527:         launcherComponent = GuestProgramLauncherComponent().apply {\r\n528:             setEnvVars(env)\r\n529:             setBox64Preset(selectedBox64Preset)\r\n530:             setGuestExecutable(buildGuestCommand(gameExePath, gameWorkDir))\r\n531:             setDeferredStart(true)\r\n532:             setTerminationCallback { status ->\r\n533:                 runOnUiThread {\r\n534:                     ShellLog.info(this@WineDisplayActivity, \"Wine guest exited status=$status\")\r\n535:                     Toast.makeText(\r\n536:                         this@WineDisplayActivity,\r\n537:                         \"游戏进程已结束 (code=$status)。\",\r\n538:                         Toast.LENGTH_SHORT\r\n539:                     ).show()\r\n540:                 }\r\n541:             }\r\n542:         }\r\n543:         environment.addComponent(launcherComponent)\r\n544:     }\r\n545: \r\n546:     private fun resolveBox64Preset(): String {\r\n547:         val requested = intent.getStringExtra(EXTRA_BOX64_PRESET).orEmpty()\r\n548:             .trim()\r\n549:             .uppercase(Locale.ENGLISH)\r\n550:         return when (requested) {\r\n551:             Box64Preset.STABILITY,\r\n552:             Box64Preset.CONSERVATIVE,\r\n553:             Box64Preset.INTERMEDIATE,\r\n554:             Box64Preset.PERFORMANCE,\r\n555:             Box64Preset.CUSTOM -> requested\r\n556:             else -> Box64Preset.PERFORMANCE\r\n557:         }\r\n558:     }\r\n559: \r\n560:     private fun resolveGraphicsDriver(): String {\r\n561:         val requested = intent.getStringExtra(EXTRA_GRAPHICS_DRIVER).orEmpty()\r\n562:             .trim()\r\n563:             .lowercase(Locale.ENGLISH)\r\n564:         if (requested.isNotBlank() && requested != \"auto\") {\r\n565:             return normalizeGraphicsDriver(requested)\r\n566:         }\r\n567:         return detectBestGraphicsDriver()\r\n568:     }\r\n569: \r\n570:     private fun normalizeGraphicsDriver(value: String): String {\r\n571:         val parts = GraphicsDrivers.parseIdentifiers(value)\r\n572:         return \"${parts[0]},${parts[1]}\"\r\n573:     }\r\n574: \r\n575:     private fun detectBestGraphicsDriver(): String {\r\n576:         val renderer = runCatching { GPUHelper.glGetRenderer(this) }.getOrDefault(\"\")\r\n577:         val hardware = buildString {\r\n578:             append(renderer).append(' ')\r\n579:             append(Build.HARDWARE).append(' ')\r\n580:             append(Build.BOARD).append(' ')\r\n581:             append(Build.MANUFACTURER).append(' ')\r\n582:             append(Build.MODEL).append(' ')\r\n583:             if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {\r\n584:                 append(Build.SOC_MANUFACTURER).append(' ')\r\n585:                 append(Build.SOC_MODEL)\r\n586:             }\r\n587:         }.lowercase(Locale.ENGLISH)\r\n588:         val vulkan = if (\r\n589:             hardware.contains(\"adreno\") ||\r\n590:             hardware.contains(\"qcom\") ||\r\n591:             hardware.contains(\"qualcomm\") ||\r\n592:             hardware.contains(\"snapdragon\")\r\n593:         ) {\r\n594:             GraphicsDrivers.TURNIP\r\n595:         } else {\r\n596:             GraphicsDrivers.DEFAULT_VULKAN_DRIVER\r\n597:         }\r\n598:         val opengl = if (\r\n599:             hardware.contains(\"mali\") ||\r\n600:             hardware.contains(\"mt\") ||\r\n601:             hardware.contains(\"mediatek\") ||\r\n602:             hardware.contains(\"exynos\")\r\n603:         ) {\r\n604:             GraphicsDrivers.VIRGL\r\n605:         } else {\r\n606:             GraphicsDrivers.DEFAULT_OPENGL_DRIVER\r\n607:         }\r\n608:         return \"$vulkan,$opengl\"\r\n609:     }\r\n610: \r\n611:     private fun applyPerformanceEnv(env: EnvVars, graphicsDriver: String) {\r\n612:         val drivers = GraphicsDrivers.parseIdentifiers(graphicsDriver)\r\n613:         env.put(\"BOX64_LOG\", \"0\")\r\n614:         env.put(\"BOX64_NOBANNER\", \"1\")\r\n615:         env.put(\"BOX64_DYNAREC\", \"1\")\r\n616:         env.put(\"BOX64_DYNAREC_FASTNAN\", \"1\")\r\n617:         env.put(\"BOX64_DYNAREC_FASTROUND\", \"1\")\r\n618:         env.put(\"BOX64_DYNAREC_BIGBLOCK\", \"3\")\r\n619:         env.put(\"BOX64_DYNAREC_FORWARD\", \"512\")\r\n620:         env.put(\"BOX64_DYNAREC_CALLRET\", \"1\")\r\n621:         env.put(\"BOX64_DYNAREC_NATIVEFLAGS\", \"1\")\r\n622:         env.put(\"BOX64_DYNAREC_WEAKBARRIER\", \"2\")\r\n623:         env.put(\"DXVK_LOG_LEVEL\", \"none\")\r\n624:         env.put(\"DXVK_STATE_CACHE_PATH\", RootFS.getDosUserCachePath())\r\n625:         env.put(\"VKD3D_SHADER_CACHE_PATH\", RootFS.getDosUserCachePath())\r\n626:         env.put(\"MESA_SHADER_CACHE_DISABLE\", \"false\")\r\n627:         // Ren'Py/SDL2 + gladio: 3.3 is more compatible than forcing 4.5.\r\n628:         env.put(\"MESA_GL_VERSION_OVERRIDE\", \"3.3\")\r\n629:         env.put(\"MESA_GLSL_VERSION_OVERRIDE\", \"330\")\r\n630:         env.put(\"vblank_mode\", \"0\")\r\n631:         env.put(\"WINEESYNC\", \"1\")\r\n632:         // Ensure Wine uses X11 driver for our XServer.\r\n633:         env.put(\"DISPLAY\", \":0\")\r\n634:         env.put(\"LIBGL_ALWAYS_SOFTWARE\", \"0\")\r\n635:         env.put(\"GALLIUM_HUD\", \"\")\r\n636: \r\n637:         if (drivers[0] == GraphicsDrivers.TURNIP) {\r\n638:             env.put(\"MESA_VK_WSI_USE_HWBUF\", \"1\")\r\n639:             env.put(\"MESA_VK_WSI_FORCE_WAIT_FOR_FENCES\", \"1\")\r\n640:             env.put(\"TU_DEBUG\", \"noconform\")\r\n641:             env.put(\"MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE\", \"1\")\r\n642:         }\r\n643:         if (drivers[1] == GraphicsDrivers.VIRGL) {\r\n644:             env.put(\"GALLIUM_DRIVER\", \"virpipe\")\r\n645:             env.put(\"LIBGL_ALWAYS_SOFTWARE\", \"0\")\r\n646:         }\r\n647:         if (drivers[1] == GraphicsDrivers.GLADIO || drivers[1] == GraphicsDrivers.ZINK) {\r\n648:             // Prefer hardware GLX path used by Winlator gladio.\r\n649:             env.put(\"MESA_LOADER_DRIVER_OVERRIDE\", \"\")\r\n650:         }\r\n651:     }\r\n652: \r\n653:     private fun buildGuestCommand(path: String, workDir: String): String {\r\n654:         val unixPath = path.removePrefix(\"file://\")\r\n655:         val exe = File(unixPath)\r\n656:         // Game folder is always mounted as D:. Prefer D:\\ relative path so Ren'Py\r\n657:         // resolves game/, renpy/, lib/ next to the executable.\r\n658:         val dosExe = when {\r\n659:             workDir.isNotBlank() &&\r\n660:                 (exe.absolutePath == workDir || exe.absolutePath.startsWith(workDir.trimEnd('/') + \"/\")) -> {\r\n661:                 val rel = exe.absolutePath\r\n662:                     .removePrefix(workDir.trimEnd('/'))\r\n663:                     .trimStart('/', '\\\\')\r\n664:                     .replace(\"/\", \"\\\\\")\r\n665:                 if (rel.isBlank()) \"D:\\\\${exe.name}\" else \"D:\\\\$rel\"\r\n666:             }\r\n667:             else -> {\r\n668:                 val mapped = toDosPath(exe.absolutePath)\r\n669:                 if (mapped.isNotBlank()) mapped else \"D:\\\\${exe.name}\"\r\n670:             }\r\n671:         }\r\n672:         val dosDir = if (dosExe.contains('\\\\')) dosExe.substringBeforeLast('\\\\') else \"D:\\\\\"\r\n673:         val escapedExe = dosExe.replace(\"\\\"\", \"\\\\\\\"\")\r\n674:         // Launch via cmd /c with cd /d so game current directory (CWD) is set to D:\\ (essential for Ren'Py & relative assets).\r\n675:         val cmd = \"wine explorer /desktop=shell,$screenInfo cmd /c \\\"cd /d $dosDir && \\\\\\\"$escapedExe\\\\\\\"\\\"\"\r\n676:         ShellLog.info(this, \"Wine guest command desktop=$screenInfo exe=$escapedExe unix=${exe.absolutePath}\")\r\n677:         return cmd\r\n678:     }\r\n679: \r\n680:     private fun toDosPath(unixPath: String): String {\r\n681:         if (unixPath.isBlank()) return \"\"\r\n682:         val abs = File(unixPath).absolutePath\r\n683:         val mapped = WineUtils.unixToDOSPath(abs, container).orEmpty()\r\n684:         // Valid DOS path looks like X:\\... or X:\r\n685:         if (mapped.matches(Regex(\"\"\"^[A-Za-z]:(\\\\.*)?$\"\"\"))) {\r\n686:             return if (mapped.length == 2) \"$mapped\\\\\" else mapped\r\n687:         }\r\n688:         // Fallback through Z: (rootfs parent)\r\n689:         return \"Z:\" + abs.replace(\"/\", \"\\\\\")\r\n690:     }\r\n691: \r\n692:     private data class PreparedGame(val exePath: String, val workDir: String)\r\n693: \r\n694:     /**\r\n695:      * Winlator-style: always mount the real game folder as D: — never copy the whole tree.\r\n696:      * Requires MANAGE_EXTERNAL_STORAGE (all-files access) for /storage/emulated/0 paths.\r\n697:      */\r\n698:     private fun prepareGameFiles(rawExePath: String, rawTreeUri: String, gameTitle: String): PreparedGame {\r\n699:         val treeUri = rawTreeUri.takeIf { it.isNotBlank() }?.let { Uri.parse(it) }\r\n700:         val hasAllFiles = hasAllFilesAccess()\r\n701:         ShellLog.info(this, \"prepareGameFiles allFiles=$hasAllFiles rawExe=$rawExePath tree=$rawTreeUri\")\r\n702: \r\n703:         // Case A: file:// or plain absolute path (preferred fast path from MainActivity).\r\n704:         val plainPath = when {\r\n705:             rawExePath.startsWith(\"file://\", ignoreCase = true) -> {\r\n706:                 Uri.parse(rawExePath).path.orEmpty().ifBlank {\r\n707:                     rawExePath.removePrefix(\"file://\")\r\n708:                 }\r\n709:             }\r\n710:             rawExePath.startsWith(\"/\") -> rawExePath\r\n711:             else -> \"\"\r\n712:         }\r\n713:         if (plainPath.isNotBlank()) {\r\n714:             val exeFile = File(plainPath)\r\n715:             if (exeFile.isFile || forceExists(exeFile)) {\r\n716:                 val workDir = exeFile.parentFile?.absolutePath.orEmpty()\r\n717:                 mountGameDrive(workDir)\r\n718:                 ShellLog.info(this, \"Direct mount (file path) D:=$workDir exe=${exeFile.name}\")\r\n719:                 return PreparedGame(exeFile.absolutePath, workDir)\r\n720:             }\r\n721:         }\r\n722: \r\n723:         // Case B: tree URI → real path under /storage/emulated/0 (Winlator model).\r\n724:         val realTreePath = treeUri?.let { resolveFilesystemPathFromUri(it) }.orEmpty()\r\n725:         if (realTreePath.isNotBlank()) {\r\n726:             val gameDir = File(realTreePath)\r\n727:             if (gameDir.isDirectory || forceExists(gameDir)) {\r\n728:                 // Prefer exe name from content URI if present; else shallow scan.\r\n729:                 val preferredName = extractExeNameFromUri(rawExePath)\r\n730:                 val exeFile = when {\r\n731:                     preferredName.isNotBlank() && File(gameDir, preferredName).let { it.isFile || forceExists(it) } ->\r\n732:                         File(gameDir, preferredName)\r\n733:                     else -> findExeInDir(gameDir)\r\n734:                 }\r\n735:                 if (exeFile != null) {\r\n736:                     mountGameDrive(gameDir.absolutePath)\r\n737:                     ShellLog.info(\r\n738:                         this,\r\n739:                         \"Direct mount (tree path) D:=${gameDir.absolutePath} exe=${exeFile.name} allFiles=$hasAllFiles\"\r\n740:                     )\r\n741:                     return PreparedGame(exeFile.absolutePath, gameDir.absolutePath)\r\n742:                 }\r\n743:                 ShellLog.info(this, \"Tree path exists but no exe found: $realTreePath\")\r\n744:             } else {\r\n745:                 ShellLog.info(this, \"Tree path not a directory: $realTreePath\")\r\n746:             }\r\n747:         }\r\n748: \r\n749:         // Case C: document URI for exe → parent folder as D:.\r\n750:         if (rawExePath.startsWith(\"content://\", ignoreCase = true)) {\r\n751:             val realExePath = resolveFilesystemPathFromUri(Uri.parse(rawExePath))\r\n752:             if (realExePath.isNotBlank()) {\r\n753:                 val exeFile = File(realExePath)\r\n754:                 if (exeFile.isFile || forceExists(exeFile)) {\r\n755:                     val workDir = exeFile.parentFile?.absolutePath.orEmpty()\r\n756:                     mountGameDrive(workDir)\r\n757:                     ShellLog.info(this, \"Direct mount (exe document) D:=$workDir\")\r\n758:                     return PreparedGame(exeFile.absolutePath, workDir)\r\n759:                 }\r\n760:             }\r\n761:         }\r\n762: \r\n763:         // No copy fallback. Tell user to grant all-files access (same as Winlator).\r\n764:         if (!hasAllFiles) {\r\n765:             runOnUiThread {\r\n766:                 Toast.makeText(\r\n767:                     this,\r\n768:                     \"需要「所有文件访问权限」才能像 Winlator 一样直接挂载游戏，请返回设置开启后重试。\",\r\n769:                     Toast.LENGTH_LONG\r\n770:                 ).show()\r\n771:             }\r\n772:             throw IllegalStateException(\r\n773:                 \"No all-files access; cannot mount $realTreePath. Grant MANAGE_EXTERNAL_STORAGE and retry.\"\r\n774:             )\r\n775:         }\r\n776: \r\n777:         throw IllegalStateException(\r\n778:             \"Unable to mount game folder. path=$realTreePath exe=$rawExePath\"\r\n779:         )\r\n780:     }\r\n781: \r\n782:     private fun hasAllFilesAccess(): Boolean {\r\n783:         return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {\r\n784:             android.os.Environment.isExternalStorageManager()\r\n785:         } else {\r\n786:             checkSelfPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE) ==\r\n787:                 android.content.pm.PackageManager.PERMISSION_GRANTED\r\n788:         }\r\n789:     }\r\n790: \r\n791:     /** Some OEM File APIs lie about canRead without all-files; existence is enough for mount. */\r\n792:     private fun forceExists(file: File): Boolean {\r\n793:         return try {\r\n794:             file.exists()\r\n795:         } catch (_: Throwable) {\r\n796:             false\r\n797:         }\r\n798:     }\r\n799: \r\n800:     private fun extractExeNameFromUri(raw: String): String {\r\nThe above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.\n"}
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
import com.rpgrtl.engine.alsaserver.ALSAClient
import com.rpgrtl.engine.container.DXWrappers
import com.rpgrtl.engine.core.AppUtils
import com.rpgrtl.engine.core.DefaultVersion
import com.rpgrtl.engine.core.EnvVars
import com.rpgrtl.engine.core.FileUtils
import com.rpgrtl.engine.core.GeneralComponents
import com.rpgrtl.engine.core.TarCompressorUtils
import com.rpgrtl.engine.core.GPUHelper
import com.rpgrtl.engine.core.WineInfo
import com.rpgrtl.engine.core.WineUtils
import com.rpgrtl.engine.widget.InputControlsView
import com.rpgrtl.engine.inputcontrols.InputControlsManager
import com.rpgrtl.engine.widget.TouchpadView
import com.rpgrtl.engine.widget.XServerView
import com.rpgrtl.engine.winhandler.WinHandler
import com.rpgrtl.engine.xconnector.UnixSocketConfig
import com.rpgrtl.engine.xenvironment.RootFS
import com.rpgrtl.engine.xenvironment.RootFSInstaller
import com.rpgrtl.engine.xenvironment.XEnvironment
import com.rpgrtl.engine.xenvironment.components.ALSAServerComponent
import com.rpgrtl.engine.xenvironment.components.GuestProgramLauncherComponent
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
    private var touchBlocked = false
    private var gameExePath = ""
    private var gameWorkDir = ""
    private var selectedBox64Preset = Box64Preset.PERFORMANCE
    private var selectedGraphicsDriver = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ShellLog.installCrashLogger(this)
        ShellLog.info(this, "WineDisplayActivity onCreate")
        AppUtils.hideSystemUI(this)
        AppUtils.keepScreenOn(this)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE

        val rawExePath = intent.getStringExtra(EXTRA_GAME_URI).orEmpty()
        val gameTreeUri = intent.getStringExtra(EXTRA_GAME_TREE_URI).orEmpty()
        val gameTitle = intent.getStringExtra(EXTRA_GAME_TITLE).orEmpty().ifBlank { "Windows Game" }
        val containerId = intent.getIntExtra(EXTRA_CONTAINER_ID, 0)
        runtimeBridge = RuntimeBridge(containerId.toString())
        ShellLog.info(
            this,
            "Wine launch requested title=$gameTitle containerId=$containerId uri=$rawExePath tree=$gameTreeUri"
        )

        if (rawExePath.isBlank()) {
            ShellLog.error(this, "Wine launch failed: blank exe path")
            Toast.makeText(this, "未找到可启动的 exe 路径。", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        rootFS = RootFS.find(this)
        if (!rootFS.isValid && !installBundledWineRuntime()) {
            ShellLog.error(this, "Wine launch failed: bundled runtime initialization failed")
            Toast.makeText(this, "内置 Winlator 运行环境初始化失败，无法启动 Ren'Py / Windows 游戏。", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        if (!prepareContainer(containerId, gameTitle)) return

        // Show a black landscape surface immediately while files prepare (can take long on SAF copy).
        val loading = FrameLayout(this).apply {
            setBackgroundColor(0xFF000000.toInt())
            systemUiVisibility = immersiveFlags()
        }
        setContentView(loading)
        Toast.makeText(this, "正在准备游戏文件并启动 Wine：$gameTitle", Toast.LENGTH_LONG).show()

        Thread {
            try {
                val prepared = prepareGameFiles(rawExePath, gameTreeUri, gameTitle)
                gameExePath = prepared.exePath
                gameWorkDir = prepared.workDir
                ShellLog.info(this, "Wine executable prepared path=$gameExePath workDir=$gameWorkDir")
                // Heavy extract + gladio path patch on worker thread (not UI).
                prepareWineRuntime()
                runOnUiThread {
                    if (isFinishing) return@runOnUiThread
                    startWineDisplay(gameTitle)
                }
            } catch (error: Throwable) {
                ShellLog.error(this, "Wine launch failed while preparing game files", error)
                runOnUiThread {
                    Toast.makeText(this, "准备游戏文件失败: ${error.message}", Toast.LENGTH_LONG).show()
                    finish()
                }
            }
        }.start()
    }

    private fun startWineDisplay(gameTitle: String) {
        // Match physical display orientation so landscape phones get a landscape X desktop.
        val dm = resources.displayMetrics
        val screenW = maxOf(dm.widthPixels, dm.heightPixels).coerceAtLeast(1280)
        val screenH = minOf(dm.widthPixels, dm.heightPixels).coerceAtLeast(720)
        val dynamicScreen = "${screenW}x${screenH}"
        container.setScreenSize(dynamicScreen)
        screenInfo = ScreenInfo(dynamicScreen)
        ShellLog.info(this, "Wine display init screen=$dynamicScreen device=${dm.widthPixels}x${dm.heightPixels}")
        xServer = XServer(this, screenInfo)
        winHandler = WinHandler(this)
        xServer.setWinHandler(winHandler)

        ShellLog.info(this, "Creating XServerView / renderer")
        xServerView = XServerView(this, xServer)
        xServer.setRenderer(xServerView.renderer)

        touchpadView = TouchpadView(this, xServer, false)
        val tp = touchpadView
        val xs = xServer
        inputControlsView = InputControlsView(this).apply {
            setXServer(xs)
            setTouchpadView(tp)
            setShowTouchscreenControls(true)
        }

        environment = XEnvironment(this, rootFS)
        addRuntimeComponents()
        setContentView(createDisplayLayout(gameTitle))

        // Defer profile loading until after layout so view has valid dimensions;
        // loadElements() converts ratio-based positions to pixels using getWidth()/getHeight()
        inputControlsView.post {
            loadDefaultControlsProfile(inputControlsView)
            inputControlsView.invalidate()
        }

        winHandler.start()
        ShellLog.info(this, "Starting Wine environment components")
        environment.startEnvironmentComponents()
        activeRuntimeBridges[container.id] = runtimeBridge
        // Verify X11 socket appeared under rootfs (host server).
        val x11 = File(rootFS.rootDir, "tmp/.X11-unix/X0")
        ShellLog.info(this, "X11 socket path=${x11.absolutePath} exists=${x11.exists()}")
        // Short delay so XServer/ALSA bind before wine attaches to DISPLAY=:0.
        Handler(Looper.getMainLooper()).postDelayed({
            val box64 = File(rootFS.rootDir, "usr/local/bin/box64")
            val wineBin = File(rootFS.rootDir, "opt/wine/bin/wine")
            val ntdll = File(rootFS.rootDir, "opt/wine/lib/wine/x86_64-unix/ntdll.so")
            val ntdllPatched = ntdll.isFile && !WinePathCompat.containsAscii(ntdll, "com.winlator")
            val box64Patched = box64.isFile && !WinePathCompat.containsAscii(box64, "com.winlator")
            ShellLog.info(
                this,
                "Starting Wine guest launcher path=$gameExePath workDir=$gameWorkDir " +
                    "x11Exists=${x11.exists()} bridgeX11=${WinePathCompat.newX11Path(this)} " +
                    "bridgeX11Exists=${File(WinePathCompat.newX11Path(this)).exists()} " +
                    "box64Exists=${box64.isFile} box64Size=${box64.length()} box64Patched=$box64Patched " +
                    "wineExists=${wineBin.isFile} ntdllPatched=$ntdllPatched " +
                    "cmd=${launcherComponent?.guestExecutable}"
            )
            try {
                // Final safety: re-patch box64 INTERP right before exec.
                val box64Ready = WinePathCompat.patchBox64Interpreter(this)
                if (!box64Ready) {
                    ShellLog.error(this, "Abort launch: box64 INTERP not patched")
                    Toast.makeText(this, "box64 解释器路径未修复，无法启动 Wine", Toast.LENGTH_LONG).show()
                    return@postDelayed
                }
                launcherComponent?.start()
                val pid = launcherComponent?.getPid() ?: -1
                ShellLog.info(this, "launcherComponent.start() returned pid=$pid")
                if (pid <= 0) {
                    Toast.makeText(this, "Wine 进程启动失败 (pid=$pid)，请查看运行日志。", Toast.LENGTH_LONG).show()
                }
            } catch (error: Throwable) {
                ShellLog.error(this, "launcherComponent.start() failed", error)
            }
        }, 900)

        Toast.makeText(this, "容器已就绪，正在启动：$gameTitle", Toast.LENGTH_SHORT).show()
    }

    private fun installBundledWineRuntime(): Boolean {
        return try {
            ShellLog.info(this, "Installing bundled Winlator runtime")
            Toast.makeText(this, "正在初始化内置 Winlator 运行环境...", Toast.LENGTH_LONG).show()
            val rootDir = rootFS.rootDir
            FileUtils.delete(rootDir)
            rootDir.mkdirs()
            val ok = TarCompressorUtils.extract(TarCompressorUtils.Type.ZSTD, this, "winlator/rootfs.tzst", rootDir)
            if (ok) rootFS.createRFSVersionFile(RootFSInstaller.LATEST_VERSION.toInt())
            ok && rootFS.isValid
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
            ShellLog.error(this, "Wine launch failed: container initialization failed")
            Toast.makeText(this, "内置 Winlator 容器初始化失败。", Toast.LENGTH_LONG).show()
            finish()
            return false
        }

        if (container.name.isNullOrBlank() || container.name.startsWith("Container-")) {
            container.setName(gameTitle)
        }
        selectedBox64Preset = resolveBox64Preset()
        selectedGraphicsDriver = resolveGraphicsDriver()
        container.setBox64Preset(selectedBox64Preset)
        container.setGraphicsDriver(selectedGraphicsDriver)
        // Ren'Py uses SDL2 OpenGL — WineD3D is safer than DXVK for pure GL titles.
        container.setDXWrapper(DXWrappers.WINED3D)
        container.setStartupSelection(Container.STARTUP_SELECTION_ESSENTIAL)
        Log.i(TAG, "Wine launch profile: box64=$selectedBox64Preset graphics=$selectedGraphicsDriver")
        ShellLog.info(this, "Wine launch profile: box64=$selectedBox64Preset graphics=$selectedGraphicsDriver")
        manager.activateContainer(container)
        return true
    }

    /**
     * Full Winlator-style prep: extract guest GPU drivers once, patch gladio package paths,
     * wineprefix tweaks. Second launch skips heavy extract (marker file).
     */
    private fun prepareWineRuntime() {
        val rootDir = rootFS.rootDir
        val marker = File(rootDir, ".winlator/rpgtl_runtime_prepared_v2")
        val drivers = GraphicsDrivers.parseIdentifiers(selectedGraphicsDriver)
        val vulkan = drivers[0]
        val opengl = drivers[1]
        val hasGladio = File(rootDir, "usr/lib/libGL.so.1.7.0").isFile ||
            File(rootDir, "usr/lib/libGL.so.1").isFile ||
            File(rootDir, "usr/lib/libGL.so").isFile
        val alreadyPrepared = marker.isFile && hasGladio

        ShellLog.info(
            this,
            "Preparing Wine runtime drivers vulkan=$vulkan opengl=$opengl prepared=$alreadyPrepared"
        )

        // Always ensure path bridge (cheap symlink) before any guest call.
        WinePathCompat.ensureBridge(this)

        if (!alreadyPrepared) {
            runOnUiThread {
                Toast.makeText(this, "首次初始化 Wine 环境（仅一次，请稍候）...", Toast.LENGTH_LONG).show()
            }

            runCatching {
                TarCompressorUtils.extract(
                    TarCompressorUtils.Type.ZSTD,
                    this,
                    "winlator/rootfs_patches.tzst",
                    rootDir
                )
            }

            try {
                GeneralComponents.extractFile(
                    GeneralComponents.Type.BOX64,
                    this,
                    DefaultVersion.BOX64,
                    DefaultVersion.BOX64
                )
                val box64 = File(rootDir, "usr/local/bin/box64")
                FileUtils.chmod(box64, 0b111_101_101) // 0755
                // Mark version so GuestProgramLauncher won't re-extract and wipe INTERP patch.
                PreferenceManager.getDefaultSharedPreferences(this)
                    .edit()
                    .putString("current_box64_version", DefaultVersion.BOX64)
                    .putString("box64_version", DefaultVersion.BOX64)
                    .apply()
                ShellLog.info(this, "Box64 extract done exists=${box64.isFile} size=${box64.length()}")
                WinePathCompat.patchBox64Interpreter(this)
            } catch (error: Throwable) {
                ShellLog.error(this, "Box64 extract failed", error)
            }

            extractDriverOnce(opengl, when (opengl) {
                GraphicsDrivers.VIRGL -> DefaultVersion.VIRGL
                GraphicsDrivers.ZINK -> DefaultVersion.ZINK
                else -> DefaultVersion.GLADIO
            })
            if (opengl != GraphicsDrivers.GLADIO) {
                extractDriverOnce(GraphicsDrivers.GLADIO, DefaultVersion.GLADIO)
            }

            extractDriverOnce(vulkan, when (vulkan) {
                GraphicsDrivers.TURNIP -> DefaultVersion.TURNIP
                GraphicsDrivers.VORTEK -> DefaultVersion.VORTEK
                else -> DefaultVersion.TURNIP
            })

            try {
                GeneralComponents.extractFile(
                    GeneralComponents.Type.DXVK,
                    this,
                    DefaultVersion.DXVK(vulkan),
                    DefaultVersion.MAJOR_DXVK
                )
                ShellLog.info(this, "DXVK extract done")
            } catch (error: Throwable) {
                ShellLog.error(this, "DXVK extract failed", error)
            }

            try {
                extractDefaultWinComponents()
            } catch (error: Throwable) {
                ShellLog.error(this, "Wincomponents extract failed", error)
            }

            try {
                WineUtils.applySystemTweaks(this, WineInfo.MAIN_WINE_INFO)
                WineUtils.changeServicesStatus(container, true)
                ShellLog.info(this, "Wineprefix system tweaks applied")
            } catch (error: Throwable) {
                ShellLog.error(this, "Wineprefix tweaks failed", error)
            }

            marker.parentFile?.mkdirs()
            FileUtils.writeString(marker, System.currentTimeMillis().toString())
            ShellLog.info(this, "Runtime marker written ${marker.absolutePath}")
        } else {
            ShellLog.info(this, "Skipping heavy extract (container already prepared)")
            runCatching {
                GeneralComponents.extractFile(
                    GeneralComponents.Type.BOX64,
                    this,
                    DefaultVersion.BOX64,
                    DefaultVersion.BOX64
                )
                FileUtils.chmod(File(rootDir, "usr/local/bin/box64"), 0b111_101_101)
                WinePathCompat.patchBox64Interpreter(this)
            }
        }

        // Patch only the files that are known to carry Winlator's package-root paths.
        // A full rootfs walk is too expensive on phones and can look like a dead launch.
        ShellLog.info(this, "Runtime path patch: core files start")
        val replaced = WinePathCompat.patchCoreRuntimePaths(this)
        ShellLog.info(this, "Runtime path patch: box64 start")
        val box64Ok = WinePathCompat.patchBox64Interpreter(this)
        ShellLog.info(this, "Runtime path patch: gladio start")
        val gladioOk = WinePathCompat.patchGuestGladio(this)
        ShellLog.info(
            this,
            "Rootfs core path rewrite replacements=$replaced box64Ok=$box64Ok gladioOk=$gladioOk " +
                "newPrefix=${WinePathCompat.newRootfsPrefix(this)}"
        )
        if (!box64Ok) {
            ShellLog.error(this, "box64 still contains com.winlator INTERP — guest will not start")
        }
    }

    private fun extractDriverOnce(name: String, version: String) {
        val ok = GeneralComponents.extractGraphicsDriverAsset(this, name, version)
        ShellLog.info(this, "Graphics driver extract $name-$version ok=$ok")
    }

    private fun extractDefaultWinComponents() {
        // Extract into the active container wineprefix (not the shared home/xuser tree only).
        val needed = listOf("directsound", "xaudio", "vcrun2010")
        val dest = File(container.getRootDir(), ".wine/drive_c/windows")
        dest.mkdirs()
        for (id in needed) {
            val asset = "winlator/wincomponents/$id.tzst"
            val ok = TarCompressorUtils.extract(TarCompressorUtils.Type.ZSTD, this, asset, dest)
            ShellLog.info(this, "Wincomponent $id extract ok=$ok dest=${dest.absolutePath}")
        }
        try {
            WineUtils.overrideWinComponentDlls(this, container, container.getWinComponents())
        } catch (error: Throwable) {
            ShellLog.error(this, "overrideWinComponentDlls failed", error)
        }
    }

    private fun loadDefaultControlsProfile(view: InputControlsView) {
        val manager = InputControlsManager(this)
        val profile = manager.getProfiles(true).firstOrNull()
        if (profile != null) {
            profile.loadElements(view)
            view.setProfile(profile)
            Log.i(TAG, "Loaded touchscreen controls profile: ${profile.name} (${profile.elements.size} elements)")
        } else {
            Log.w(TAG, "No touchscreen controls profile found; virtual controls will be empty.")
        }
    }

    private fun addRuntimeComponents() {
        WinePathCompat.ensureBridge(this)

        val rootDir = rootFS.rootDir
        // Prefer short bridge path for sockets so guest libs (patched to .../files/w) match.
        val bridgeRoot = WinePathCompat.shortRootfsLink(this).let {
            if (it.exists()) it.absolutePath else rootDir.absolutePath
        }
        val drivers = GraphicsDrivers.parseIdentifiers(selectedGraphicsDriver)
        val vulkan = drivers[0]
        val opengl = drivers[1]

        File(rootDir, "tmp/.X11-unix").mkdirs()
        File(rootDir, "tmp/.sound").mkdirs()
        File(rootDir, "tmp/.sysvshm").mkdirs()
        File(rootDir, "tmp/shm").mkdirs()

        // Host X server listens on real rootfs path; bridge symlink makes .../w/tmp/... the same inode.
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

        if (opengl == GraphicsDrivers.VIRGL) {
            environment.addComponent(
                VirGLRendererComponent(
                    xServer,
                    UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.VIRGL_SERVER_PATH)
                )
            )
            ShellLog.info(this, "VirGLRendererComponent added")
        }

        environment.addComponent(
            ALSAServerComponent(
                UnixSocketConfig.create(rootDir.absolutePath, UnixSocketConfig.ALSA_SERVER_PATH),
                ALSAClient.Options()
            )
        )

        val winePrefix = File(container.getRootDir(), ".wine").absolutePath
        // Guest-facing paths must use the SHORT bridge prefix (what we patched into .so files).
        val guestRoot = WinePathCompat.newRootfsPrefix(this)
        val alsaSocket = "$guestRoot${UnixSocketConfig.ALSA_SERVER_PATH}"
        val sysvSocket = "$guestRoot${UnixSocketConfig.SYSVSHM_SERVER_PATH}"
        val tmpDir = "$guestRoot/tmp"
        val env = EnvVars(container.envVars)
        env.put("WINEPREFIX", winePrefix)
        env.put("HOME", rootDir.absolutePath + RootFS.HOME_PATH)
        // Critical: Xlib builds /tmp/.X11-unix from TMPDIR on some builds; always set both.
        env.put("TMPDIR", tmpDir)
        env.put("TEMP", tmpDir)
        env.put("TMP", tmpDir)
        env.put("DISPLAY", ":0")
        env.put("WINEDLLOVERRIDES", "winemenubuilder.exe=d;mscoree,mshtml=")
        env.put("ANDROID_ALSA_SERVER", alsaSocket)
        env.put("ANDROID_SYSVSHM_SERVER", sysvSocket)
        env.put("ALSA_PLUGIN_DIR", "$guestRoot/usr/lib/alsa-lib")
        env.put("SDL_AUDIODRIVER", "alsa")
        env.put("PULSE_SERVER", "")
        env.put("BOX64_LOG", "1")
        env.put("BOX64_NOBANNER", "0")
        env.put("WINEDEBUG", "-all,+err,+fix")
        env.put("NWJS_ARGS", "--remote-debugging-port=${RuntimeBridge.CDP_PORT}")
        env.put("CHROME_REMOTE_DEBUGGING_PORT", RuntimeBridge.CDP_PORT.toString())
        if (gameWorkDir.isNotBlank()) {
            env.put("WINEPATH", gameWorkDir)
        }
        applyPerformanceEnv(env, selectedGraphicsDriver)
        ShellLog.info(
            this,
            "Runtime env ready vulkan=$vulkan opengl=$opengl winePrefix=$winePrefix " +
                "guestRoot=$guestRoot alsa=$alsaSocket tmp=$tmpDir x11=${WinePathCompat.newX11Path(this)} " +
                "bridgeRoot=$bridgeRoot"
        )

        com.rpgrtl.engine.core.ProcessHelper.removeAllDebugCallbacks()
        com.rpgrtl.engine.core.ProcessHelper.addDebugCallback { line ->
            if (line.isNullOrBlank()) return@addDebugCallback
            val text = line.trim()
            if (text.isEmpty()) return@addDebugCallback
            ShellLog.info(this@WineDisplayActivity, "WINE: $text")
            Log.i(TAG, "WINE: $text")
        }

        launcherComponent = GuestProgramLauncherComponent().apply {
            setEnvVars(env)
            setBox64Preset(selectedBox64Preset)
            setGuestExecutable(buildGuestCommand(gameExePath, gameWorkDir))
            setDeferredStart(true)
            setTerminationCallback { status ->
                runOnUiThread {
                    ShellLog.info(this@WineDisplayActivity, "Wine guest exited status=$status")
                    Toast.makeText(
                        this@WineDisplayActivity,
                        "游戏进程已结束 (code=$status)。",
                        Toast.LENGTH_SHORT
                    ).show()
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
        // Ren'Py/SDL2 + gladio: 3.3 is more compatible than forcing 4.5.
        env.put("MESA_GL_VERSION_OVERRIDE", "3.3")
        env.put("MESA_GLSL_VERSION_OVERRIDE", "330")
        env.put("vblank_mode", "0")
        env.put("WINEESYNC", "1")
        // Ensure Wine uses X11 driver for our XServer.
        env.put("DISPLAY", ":0")
        env.put("LIBGL_ALWAYS_SOFTWARE", "0")
        env.put("GALLIUM_HUD", "")

        if (drivers[0] == GraphicsDrivers.TURNIP) {
            env.put("MESA_VK_WSI_USE_HWBUF", "1")
            env.put("MESA_VK_WSI_FORCE_WAIT_FOR_FENCES", "1")
            env.put("TU_DEBUG", "noconform")
            env.put("MESA_VK_DEVICE_SELECT_FORCE_DEFAULT_DEVICE", "1")
        }
        if (drivers[1] == GraphicsDrivers.VIRGL) {
            env.put("GALLIUM_DRIVER", "virpipe")
            env.put("LIBGL_ALWAYS_SOFTWARE", "0")
        }
        if (drivers[1] == GraphicsDrivers.GLADIO || drivers[1] == GraphicsDrivers.ZINK) {
            // Prefer hardware GLX path used by Winlator gladio.
            env.put("MESA_LOADER_DRIVER_OVERRIDE", "")
        }
    }

    private fun buildGuestCommand(path: String, workDir: String): String {
        val unixPath = path.removePrefix("file://")
        val exe = File(unixPath)
        // Game folder is always mounted as D:. Prefer D:\ relative path so Ren'Py
        // resolves game/, renpy/, lib/ next to the executable.
        val dosExe = when {
            workDir.isNotBlank() &&
                (exe.absolutePath == workDir || exe.absolutePath.startsWith(workDir.trimEnd('/') + "/")) -> {
                val rel = exe.absolutePath
                    .removePrefix(workDir.trimEnd('/'))
                    .trimStart('/', '\\')
                    .replace("/", "\\")
                if (rel.isBlank()) "D:\\${exe.name}" else "D:\\$rel"
            }
            else -> {
                val mapped = toDosPath(exe.absolutePath)
                if (mapped.isNotBlank()) mapped else "D:\\${exe.name}"
            }
        }
        val dosDir = if (dosExe.contains('\\')) dosExe.substringBeforeLast('\\') else "D:\\"
        val escapedExe = dosExe.replace("\"", "\\\"")
        // Launch via cmd /c with cd /d so game current directory (CWD) is set to D:\ (essential for Ren'Py & relative assets).
        val cmd = "wine explorer /desktop=shell,$screenInfo cmd /c \"cd /d $dosDir && \\\"$escapedExe\\\"\""
        ShellLog.info(this, "Wine guest command desktop=$screenInfo exe=$escapedExe unix=${exe.absolutePath}")
        return cmd
    }

    private fun toDosPath(unixPath: String): String {
        if (unixPath.isBlank()) return ""
        val abs = File(unixPath).absolutePath
        val mapped = WineUtils.unixToDOSPath(abs, container).orEmpty()
        // Valid DOS path looks like X:\... or X:
        if (mapped.matches(Regex("""^[A-Za-z]:(\\.*)?$"""))) {
            return if (mapped.length == 2) "$mapped\\" else mapped
        }
        // Fallback through Z: (rootfs parent)
        return "Z:" + abs.replace("/", "\\")
    }

    private data class PreparedGame(val exePath: String, val workDir: String)

    /**
     * Winlator-style: always mount the real game folder as D: — never copy the whole tree.
     * Requires MANAGE_EXTERNAL_STORAGE (all-files access) for /storage/emulated/0 paths.
     */
    private fun prepareGameFiles(rawExePath: String, rawTreeUri: String, gameTitle: String): PreparedGame {
        val treeUri = rawTreeUri.takeIf { it.isNotBlank() }?.let { Uri.parse(it) }
        val hasAllFiles = hasAllFilesAccess()
        ShellLog.info(this, "prepareGameFiles allFiles=$hasAllFiles rawExe=$rawExePath tree=$rawTreeUri")

        // Case A: file:// or plain absolute path (preferred fast path from MainActivity).
        val plainPath = when {
            rawExePath.startsWith("file://", ignoreCase = true) -> {
                Uri.parse(rawExePath).path.orEmpty().ifBlank {
                    rawExePath.removePrefix("file://")
                }
            }
            rawExePath.startsWith("/") -> rawExePath
            else -> ""
        }
        if (plainPath.isNotBlank()) {
            val exeFile = File(plainPath)
            if (exeFile.isFile || forceExists(exeFile)) {
                val workDir = exeFile.parentFile?.absolutePath.orEmpty()
                mountGameDrive(workDir)
                ShellLog.info(this, "Direct mount (file path) D:=$workDir exe=${exeFile.name}")
                return PreparedGame(exeFile.absolutePath, workDir)
            }
        }

        // Case B: tree URI → real path under /storage/emulated/0 (Winlator model).
        val realTreePath = treeUri?.let { resolveFilesystemPathFromUri(it) }.orEmpty()
        if (realTreePath.isNotBlank()) {
            val gameDir = File(realTreePath)
            if (gameDir.isDirectory || forceExists(gameDir)) {
                // Prefer exe name from content URI if present; else shallow scan.
                val preferredName = extractExeNameFromUri(rawExePath)
                val exeFile = when {
                    preferredName.isNotBlank() && File(gameDir, preferredName).let { it.isFile || forceExists(it) } ->
                        File(gameDir, preferredName)
                    else -> findExeInDir(gameDir)
                }
                if (exeFile != null) {
                    mountGameDrive(gameDir.absolutePath)
                    ShellLog.info(
                        this,
                        "Direct mount (tree path) D:=${gameDir.absolutePath} exe=${exeFile.name} allFiles=$hasAllFiles"
                    )
                    return PreparedGame(exeFile.absolutePath, gameDir.absolutePath)
                }
                ShellLog.info(this, "Tree path exists but no exe found: $realTreePath")
            } else {
                ShellLog.info(this, "Tree path not a directory: $realTreePath")
            }
        }

        // Case C: document URI for exe → parent folder as D:.
        if (rawExePath.startsWith("content://", ignoreCase = true)) {
            val realExePath = resolveFilesystemPathFromUri(Uri.parse(rawExePath))
            if (realExePath.isNotBlank()) {
                val exeFile = File(realExePath)
                if (exeFile.isFile || forceExists(exeFile)) {
                    val workDir = exeFile.parentFile?.absolutePath.orEmpty()
                    mountGameDrive(workDir)
                    ShellLog.info(this, "Direct mount (exe document) D:=$workDir")
                    return PreparedGame(exeFile.absolutePath, workDir)
                }
            }
        }

        // No copy fallback. Tell user to grant all-files access (same as Winlator).
        if (!hasAllFiles) {
            runOnUiThread {
                Toast.makeText(
                    this,
                    "需要「所有文件访问权限」才能像 Winlator 一样直接挂载游戏，请返回设置开启后重试。",
                    Toast.LENGTH_LONG
                ).show()
            }
            throw IllegalStateException(
                "No all-files access; cannot mount $realTreePath. Grant MANAGE_EXTERNAL_STORAGE and retry."
            )
        }

        throw IllegalStateException(
            "Unable to mount game folder. path=$realTreePath exe=$rawExePath"
        )
    }

    private fun hasAllFilesAccess(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            android.os.Environment.isExternalStorageManager()
        } else {
            checkSelfPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE) ==
                android.content.pm.PackageManager.PERMISSION_GRANTED
        }
    }

    /** Some OEM File APIs lie about canRead without all-files; existence is enough for mount. */
    private fun forceExists(file: File): Boolean {
        return try {
            file.exists()
        } catch (_: Throwable) {
            false
        }
    }

    private fun extractExeNameFromUri(raw: String): String {

package com.rpgrtl.shell.ui

import android.content.BroadcastReceiver
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.documentfile.provider.DocumentFile
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.rpgrtl.shell.data.GameRepository
import com.rpgrtl.shell.data.TranslationManager
import com.rpgrtl.shell.data.model.GameItem
import com.rpgrtl.shell.ui.hotreload.HotReloadScreen
import com.rpgrtl.shell.ui.library.LibraryScreen
import com.rpgrtl.shell.ui.navigation.Screen
import com.rpgrtl.shell.ui.navigation.inGameNavScreens
import com.rpgrtl.shell.ui.navigation.workspaceNavScreens
import com.rpgrtl.shell.ui.pclink.PcLinkScreen
import com.rpgrtl.shell.ui.settings.SettingsScreen
import com.rpgrtl.shell.ui.theme.RPGRenPyLocalizerTheme
import com.rpgrtl.shell.ui.trainer.TrainerScreen
import com.rpgrtl.shell.ui.winlator.WinlatorConfigScreen
import com.rpgrtl.shell.ui.workbench.TranslationScreen
import com.rpgrtl.shell.wine.WinlatorBridge
import java.io.File

@Composable
fun MainScreen(incomingIntent: Intent? = null) {
    val context = LocalContext.current
    val navController = rememberNavController()
    val repository = remember { GameRepository(context) }

    val games = remember { mutableStateListOf<GameItem>() }
    var isRefreshing by remember { mutableStateOf(false) }
    var activeGame by remember { mutableStateOf<GameItem?>(null) }
    var dynamicColor by remember { mutableStateOf(true) }
    var isGameRunning by remember { mutableStateOf(false) }
    var translationRefreshTrigger by remember { mutableIntStateOf(0) }

    fun refreshGames() {
        isRefreshing = true
        games.clear()
        games.addAll(repository.getGames())
        if (activeGame == null && games.isNotEmpty()) {
            activeGame = games.first()
        }
        isRefreshing = false
    }

    LaunchedEffect(Unit) {
        refreshGames()
    }

    // 监听游戏运行状态广播（用于游戏前/游戏后双状态 Tab 切换）
    DisposableEffect(Unit) {
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: android.content.Context?, intent: Intent?) {
                val running = intent?.getBooleanExtra("running", false) ?: false
                isGameRunning = running
                val gameDir = intent?.getStringExtra("game_dir")
                if (running && !gameDir.isNullOrBlank()) {
                    val matched = games.find { it.folderPath.equals(gameDir, ignoreCase = true) }
                    if (matched != null) {
                        activeGame = matched
                    }
                }
                if (!running) {
                    // 游戏退出时自动导航回游戏库
                    navController.navigate(Screen.Library.route) {
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        launchSingleTop = true
                        restoreState = true
                    }
                }
            }
        }
        val filter = IntentFilter("com.rpgrtl.GAME_STATE")
        LocalBroadcastManager.getInstance(context).registerReceiver(receiver, filter)
        onDispose {
            LocalBroadcastManager.getInstance(context).unregisterReceiver(receiver)
        }
    }

    LaunchedEffect(incomingIntent) {
        if (incomingIntent != null) {
            val targetPage = incomingIntent.getStringExtra("target_page")
            val gamePath = incomingIntent.getStringExtra("game_path")
            val gameTitle = incomingIntent.getStringExtra("game_title")

            if (!gamePath.isNullOrBlank() || !gameTitle.isNullOrBlank()) {
                val matched = games.find {
                    (gamePath != null && (it.folderPath.equals(gamePath, ignoreCase = true) || it.executablePath.equals(gamePath, ignoreCase = true))) ||
                    (gameTitle != null && it.title.equals(gameTitle, ignoreCase = true))
                }
                if (matched != null) {
                    activeGame = matched
                } else if (!gamePath.isNullOrBlank()) {
                    val f = File(gamePath)
                    val dir = if (f.isDirectory) f else f.parentFile ?: f
                    val imported = repository.importGameFromDirectory(dir) ?: GameItem(
                        id = java.util.UUID.randomUUID().toString(),
                        title = gameTitle?.ifBlank { f.nameWithoutExtension } ?: f.nameWithoutExtension,
                        folderPath = dir.absolutePath,
                        executablePath = f.absolutePath,
                        engine = repository.detectEngine(dir)
                    )
                    activeGame = imported
                    refreshGames()
                }
            }

            when (targetPage) {
                "trainer", "data" -> {
                    navController.navigate(Screen.Trainer.route) {
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        launchSingleTop = true
                        restoreState = true
                    }
                }
                "translate", "workbench" -> {
                    navController.navigate(Screen.Workbench.route) {
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        launchSingleTop = true
                        restoreState = true
                    }
                }
                "runtime", "winlator" -> {
                    navController.navigate(Screen.Winlator.route) {
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        launchSingleTop = true
                        restoreState = true
                    }
                }
            }
        }
    }

    // SAF 文件夹选择器：用户选择包含游戏的游戏目录
    val folderPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocumentTree()
    ) { uri: Uri? ->
        if (uri != null) {
            try {
                // 授权持久化
                context.contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                )
                val doc = DocumentFile.fromTreeUri(context, uri)
                if (doc != null) {
                    val rawPath = doc.uri.path.orEmpty()
                    val actualDir = resolveActualFolder(context, uri, doc)
                    if (actualDir != null && actualDir.isDirectory) {
                        val imported = repository.importGameFromDirectory(actualDir)
                        if (imported != null) {
                            activeGame = imported
                            refreshGames()
                            Toast.makeText(context, "已成功导入: ${imported.title}", Toast.LENGTH_SHORT).show()
                        } else {
                            Toast.makeText(context, "未在所选目录中检测到可运行的游戏启动文件", Toast.LENGTH_LONG).show()
                        }
                    } else {
                        Toast.makeText(context, "已选择目录: $rawPath", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
                Toast.makeText(context, "导入出错: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    // SAF 翻译文件导入选择器
    val importTranslationLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null && activeGame != null) {
            try {
                val content = context.contentResolver.openInputStream(uri)?.use { stream ->
                    stream.bufferedReader(Charsets.UTF_8).readText()
                }
                if (!content.isNullOrBlank()) {
                    val gameDir = File(activeGame!!.folderPath)
                    val targetFile = TranslationManager.getDefaultTranslationFile(gameDir)
                    targetFile.writeText(content, Charsets.UTF_8)
                    Toast.makeText(context, "翻译文件已成功导入并覆盖", Toast.LENGTH_SHORT).show()
                    translationRefreshTrigger++
                }
            } catch (e: Exception) {
                Toast.makeText(context, "导入翻译文件失败: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    // SAF 翻译文件导出选择器
    val exportTranslationLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("application/json")
    ) { uri: Uri? ->
        if (uri != null && activeGame != null) {
            try {
                val gameDir = File(activeGame!!.folderPath)
                val transFile = TranslationManager.findTranslationFile(gameDir)
                if (transFile != null && transFile.exists()) {
                    val content = transFile.readText(Charsets.UTF_8)
                    context.contentResolver.openOutputStream(uri)?.use { stream ->
                        stream.bufferedWriter(Charsets.UTF_8).use { it.write(content) }
                    }
                    Toast.makeText(context, "翻译文件导出成功", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(context, "当前游戏未检测到翻译文件", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Toast.makeText(context, "导出失败: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    RPGRenPyLocalizerTheme(dynamicColor = dynamicColor) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            contentWindowInsets = WindowInsets(0, 0, 0, 0),
            bottomBar = {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentRoute = navBackStackEntry?.destination?.route
                val currentNavScreens = if (isGameRunning) inGameNavScreens else workspaceNavScreens

                NavigationBar(
                    containerColor = MaterialTheme.colorScheme.surface
                ) {
                    currentNavScreens.forEach { screen ->
                        NavigationBarItem(
                            icon = { Icon(screen.icon, contentDescription = screen.title) },
                            label = { Text(screen.title) },
                            selected = currentRoute == screen.route,
                            onClick = {
                                if (currentRoute != screen.route) {
                                    navController.navigate(screen.route) {
                                        popUpTo(navController.graph.findStartDestination().id) {
                                            saveState = true
                                        }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                }
                            }
                        )
                    }
                }
            }
        ) { innerPadding ->
            NavHost(
                navController = navController,
                startDestination = Screen.Library.route,
                modifier = Modifier.padding(innerPadding)
            ) {
                // 1. 游戏库页面
                composable(Screen.Library.route) {
                    LibraryScreen(
                        games = games,
                        isRefreshing = isRefreshing,
                        onRefresh = { refreshGames() },
                        onAddGame = { folderPickerLauncher.launch(null) },
                        onLaunchGame = { game ->
                            activeGame = game
                            WinlatorBridge.launchGame(context, game)
                        },
                        onOpenTranslation = { game ->
                            activeGame = game
                            navController.navigate(Screen.Workbench.route)
                        },
                        onOpenTrainer = { game ->
                            activeGame = game
                            navController.navigate(Screen.Trainer.route)
                        },
                        onDeleteGame = { game ->
                            repository.removeGame(game.id)
                            if (activeGame?.id == game.id) {
                                activeGame = null
                            }
                            refreshGames()
                        },
                        onUpdatePreset = { game, box64, driver ->
                            val updated = game.copy(box64Preset = box64, graphicsDriver = driver)
                            repository.updateGame(updated)
                            refreshGames()
                        }
                    )
                }

                // 2. 翻译工作台页面（仅统计卡片与导入导出，零卡顿）
                composable(Screen.Workbench.route) {
                    TranslationScreen(
                        activeGame = activeGame,
                        onPickGame = {
                            navController.navigate(Screen.Library.route)
                        },
                        onImportFile = {
                            importTranslationLauncher.launch(arrayOf("application/json", "text/*", "*/*"))
                        },
                        onExportFile = {
                            val defaultName = "${activeGame?.title?.replace(" ", "_") ?: "translation"}.json"
                            exportTranslationLauncher.launch(defaultName)
                        },
                        refreshTrigger = translationRefreshTrigger
                    )
                }

                // 3. 游戏运行中：翻译热重载页面
                composable(Screen.HotReload.route) {
                    HotReloadScreen(
                        activeGame = activeGame,
                        onInject = {
                            val gameDir = activeGame?.folderPath.orEmpty()
                            LocalBroadcastManager.getInstance(context).sendBroadcast(
                                Intent("com.rpgrtl.RELOAD_TRANSLATIONS").apply {
                                    putExtra("game_dir", gameDir)
                                }
                            )
                        }
                    )
                }

                // 4. 游戏运行中：作弊修改器页面（路由守卫：仅游戏运行中可见）
                composable(Screen.Trainer.route) {
                    LaunchedEffect(isGameRunning) {
                        if (!isGameRunning) {
                            navController.navigate(Screen.Library.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    }
                    TrainerScreen(
                        activeGame = activeGame,
                        onPickGame = {
                            navController.navigate(Screen.Library.route)
                        }
                    )
                }

                // 4. Winlator 容器配置页面
                composable(Screen.Winlator.route) {
                    WinlatorConfigScreen(
                        activeGame = activeGame,
                        onLaunchActiveGame = {
                            activeGame?.let { WinlatorBridge.launchGame(context, it) }
                        }
                    )
                }

                // 保留 PC 联动路由（不在 Tab 中暴露）
                composable(Screen.PcLink.route) {
                    PcLinkScreen(
                        activeGame = activeGame,
                        onPickGame = {
                            navController.navigate(Screen.Library.route)
                        }
                    )
                }

                // 5. 设置页面
                composable(Screen.Settings.route) {
                    SettingsScreen(
                        dynamicColor = dynamicColor,
                        onDynamicColorChange = { dynamicColor = it }
                    )
                }
            }
        }
    }
}

/**
 * 辅助将 SAF TreeUri 解析为 Android 物理路径（优先 /storage/emulated/0）
 */
private fun resolveActualFolder(context: android.content.Context, uri: Uri, doc: DocumentFile): File? {
    val path = uri.path.orEmpty()
    // 典型 SAF 路径: /tree/primary:Download/GameFolder
    if (path.contains("primary:")) {
        val rel = path.substringAfter("primary:").trimStart('/')
        val extDir = android.os.Environment.getExternalStorageDirectory()
        val cand = File(extDir, rel)
        if (cand.exists() && cand.isDirectory) return cand
    }
    // 外部存储直接访问
    val docUri = doc.uri.path.orEmpty()
    if (docUri.startsWith("/storage/")) {
        val f = File(docUri)
        if (f.exists() && f.isDirectory) return f
    }
    // 回退到应用外部私有缓存路径或返回外部存储根目录
    return android.os.Environment.getExternalStorageDirectory()
}

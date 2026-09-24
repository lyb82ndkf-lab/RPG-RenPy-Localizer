package com.rpgrtl.shell.data

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.rpgrtl.shell.data.model.GameEngine
import com.rpgrtl.shell.data.model.GameItem
import java.io.File
import java.nio.charset.StandardCharsets
import java.util.UUID

class GameRepository(private val context: Context) {
    private val gson = Gson()
    private val libraryFile: File
        get() = File(context.filesDir, "games_library.json")

    /**
     * 获取所有已导入的游戏
     */
    fun getGames(): List<GameItem> {
        if (!libraryFile.exists()) return emptyList()
        return try {
            val json = libraryFile.readText(StandardCharsets.UTF_8)
            val listType = object : TypeToken<List<GameItem>>() {}.type
            val list: List<GameItem> = gson.fromJson(json, listType) ?: emptyList()
            // 实时刷新翻译文件状态，并自动修复被错误识别为 UnityCrashHandler 的启动文件
            var needSave = false
            val refreshed = list.map { game ->
                var g = refreshTranslationStats(game)
                val currentExeName = g.executableFile.name.lowercase()
                if (currentExeName.startsWith("unitycrashhandler") || !g.executableFile.exists()) {
                    val realExe = findExecutable(g.directory)
                    if (realExe != null && realExe.absolutePath != g.executablePath) {
                        g = g.copy(executablePath = realExe.absolutePath)
                        needSave = true
                    }
                }
                g
            }
            if (needSave) {
                saveGames(refreshed)
            }
            refreshed
        } catch (e: Exception) {
            e.printStackTrace()
            emptyList()
        }
    }

    /**
     * 保存游戏列表
     */
    fun saveGames(games: List<GameItem>) {
        try {
            val json = gson.toJson(games)
            libraryFile.writeText(json, StandardCharsets.UTF_8)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    /**
     * 导入单个游戏目录
     */
    fun importGameFromDirectory(dir: File): GameItem? {
        if (!dir.exists() || !dir.isDirectory) return null

        val engine = detectEngine(dir)

        // RPG Maker MV/MZ 用 WebView 运行，不强制要求 exe 文件
        val exe: File = if (engine == GameEngine.RPG_MAKER_MV_MZ) {
            // 优先找真实 exe，找不到就用 index.html 作为占位路径
            findExecutable(dir)
                ?: File(dir, "www/index.html").takeIf { it.isFile }
                ?: File(dir, "index.html").takeIf { it.isFile }
                ?: return null
        } else {
            findExecutable(dir) ?: return null
        }

        val transFile = TranslationManager.findTranslationFile(dir)
        val transItems = transFile?.let { TranslationManager.loadTranslations(it) } ?: emptyList()
        val translated = transItems.count { it.target.isNotBlank() }

        val game = GameItem(
            id = UUID.randomUUID().toString(),
            title = dir.name,
            folderPath = dir.absolutePath,
            executablePath = exe.absolutePath,
            engine = engine,
            lastPlayedTime = System.currentTimeMillis(),
            translationFileExists = transFile != null,
            translatedCount = translated,
            totalCount = transItems.size
        )

        val current = getGames().toMutableList()
        current.removeAll { it.folderPath == game.folderPath }
        current.add(0, game)
        saveGames(current)
        return game
    }

    /**
     * 更新游戏项配置
     */
    fun updateGame(updated: GameItem) {
        val current = getGames().toMutableList()
        val index = current.indexOfFirst { it.id == updated.id }
        if (index >= 0) {
            current[index] = updated
            saveGames(current)
        }
    }

    /**
     * 删除游戏
     */
    fun removeGame(id: String) {
        val current = getGames().toMutableList()
        current.removeAll { it.id == id }
        saveGames(current)
    }

    /**
     * 刷新游戏的翻译文件状态
     */
    fun refreshTranslationStats(game: GameItem): GameItem {
        val dir = File(game.folderPath)
        if (!dir.exists()) return game

        val transFile = TranslationManager.findTranslationFile(dir)
        if (transFile == null || !transFile.exists()) {
            return game.copy(translationFileExists = false, translatedCount = 0, totalCount = 0)
        }

        val items = TranslationManager.loadTranslations(transFile)
        val translated = items.count { it.target.isNotBlank() }
        return game.copy(
            translationFileExists = true,
            translatedCount = translated,
            totalCount = items.size
        )
    }

    /**
     * 自动检测游戏引擎类型
     */
    fun detectEngine(folder: File): GameEngine {
        val files = folder.listFiles() ?: return GameEngine.CUSTOM
        val names = files.map { it.name.lowercase() }.toSet()

        // 1. RPG Maker MV / MZ
        if (names.contains("package.json") ||
            File(folder, "data/System.json").exists() ||
            File(folder, "www/data/System.json").exists()
        ) {
            return GameEngine.RPG_MAKER_MV_MZ
        }

        // 2. RPG Developer Bakin
        if (names.any { it.contains("bakin") } ||
            File(folder, "Data/Project.json").exists() ||
            File(folder, "BakinLauncher.exe").exists()
        ) {
            return GameEngine.BAKIN
        }

        // 3. Wolf RPG Editor
        if (names.contains("data.wolf") ||
            names.contains("game.dat") ||
            File(folder, "Data/BasicData").exists() ||
            files.any { it.extension.lowercase() == "mps" }
        ) {
            return GameEngine.WOLF_RPG
        }

        // 4. Ren'Py
        if (names.contains("renpy") ||
            File(folder, "game").isDirectory &&
            (File(folder, "game").listFiles()?.any { it.extension.lowercase() in listOf("rpa", "rpyc", "rpy") } == true)
        ) {
            return GameEngine.RENPY
        }

        // 5. RPG Maker XP / VX / VX Ace / 2000 / 2003
        if (names.contains("game.rgss3a") ||
            names.contains("game.rgss2a") ||
            names.contains("game.rgssad") ||
            names.contains("rpg_rt.exe") ||
            File(folder, "Data/Scripts.rxdata").exists() ||
            File(folder, "Data/Scripts.rvdata2").exists()
        ) {
            return GameEngine.RPG_MAKER_LEGACY
        }

        // 6. TyranoScript
        if (File(folder, "data/scenario").exists() || File(folder, "tyrano").exists()) {
            return GameEngine.TYRANO
        }

        // 7. Unity
        if (names.contains("unityplayer.dll") || files.any { it.isDirectory && it.name.endsWith("_Data") }) {
            return GameEngine.UNITY
        }

        return GameEngine.CUSTOM
    }

    /**
     * 智能寻找游戏目录下的主可执行文件
     */
    fun findExecutable(folder: File): File? {
        val files = folder.listFiles() ?: return null

        fun isIgnoredExe(name: String): Boolean {
            val lower = name.lowercase()
            return lower.startsWith("unitycrashhandler") ||
                   lower.startsWith("unins") ||
                   lower.startsWith("uninstall") ||
                   lower.startsWith("update") ||
                   lower.startsWith("patcher") ||
                   lower.startsWith("crashpad") ||
                   lower.startsWith("crashreport") ||
                   lower.startsWith("dxsetup") ||
                   lower.startsWith("vcredist")
        }

        // 1. 针对 Unity 游戏的精准配对：
        // Unity 游戏目录结构为 <GameName>.exe 对应同名的 <GameName>_Data 文件夹
        val unityDataDir = files.firstOrNull { it.isDirectory && it.name.endsWith("_Data", ignoreCase = true) }
        if (unityDataDir != null) {
            val baseName = unityDataDir.name.substring(0, unityDataDir.name.length - 5) // 去掉 "_Data"
            val matchedExe = files.firstOrNull {
                it.isFile && it.extension.equals("exe", ignoreCase = true) &&
                !isIgnoredExe(it.name) &&
                it.nameWithoutExtension.equals(baseName, ignoreCase = true)
            }
            if (matchedExe != null) return matchedExe
        }

        // 2. 优先匹配标准启动文件名
        val preferredNames = listOf(
            "game.exe",
            "bakinlauncher.exe",
            "start.exe",
            "launch.exe",
            "launcher.exe",
            "nw.exe",
            "rpg_rt.exe"
        )

        for (pref in preferredNames) {
            val found = files.firstOrNull { it.isFile && it.name.equals(pref, ignoreCase = true) && !isIgnoredExe(it.name) }
            if (found != null) return found
        }

        // 3. 寻找其它有效 .exe（严格排除 UnityCrashHandler、卸载器等）
        val exeList = files.filter {
            it.isFile && it.extension.equals("exe", ignoreCase = true) && !isIgnoredExe(it.name)
        }

        if (exeList.isEmpty()) return null

        // 优先匹配与父文件夹同名（或包含相同关键词）的 exe
        val folderNamedExe = exeList.firstOrNull {
            it.nameWithoutExtension.equals(folder.name, ignoreCase = true) ||
            folder.name.contains(it.nameWithoutExtension, ignoreCase = true) ||
            it.nameWithoutExtension.contains(folder.name, ignoreCase = true)
        }
        if (folderNamedExe != null) return folderNamedExe

        // 否则选择体积最大的主程序
        return exeList.maxByOrNull { it.length() }
    }
}

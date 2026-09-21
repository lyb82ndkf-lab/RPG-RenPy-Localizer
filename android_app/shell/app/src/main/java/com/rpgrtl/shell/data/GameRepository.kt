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
            // 实时刷新翻译文件状态
            list.map { refreshTranslationStats(it) }
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

        // 优先匹配标准名称
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
            val found = files.firstOrNull { it.isFile && it.name.equals(pref, ignoreCase = true) }
            if (found != null) return found
        }

        // 寻找任意 .exe（排除常见的卸载或更新程序）
        val ignoredNames = setOf("unins000.exe", "uninstall.exe", "update.exe", "unitycrashhandler.exe")
        val exeList = files.filter {
            it.isFile && it.extension.equals("exe", ignoreCase = true) && !ignoredNames.contains(it.name.lowercase())
        }

        return exeList.maxByOrNull { it.length() }
    }
}

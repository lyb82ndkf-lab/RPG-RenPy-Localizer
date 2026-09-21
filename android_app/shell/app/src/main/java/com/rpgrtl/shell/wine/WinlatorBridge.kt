package com.rpgrtl.shell.wine

import android.content.Context
import android.content.Intent
import android.widget.Toast
import com.rpgrtl.shell.data.TranslationManager
import com.rpgrtl.shell.data.model.ContainerConfig
import com.rpgrtl.shell.data.model.GameEngine
import com.rpgrtl.shell.data.model.GameItem
import java.io.File

object WinlatorBridge {

    /**
     * 准备并启动游戏至 Winlator Wine 容器
     */
    fun launchGame(context: Context, game: GameItem, containerConfig: ContainerConfig? = null) {
        val gameDir = File(game.folderPath)

        // ── RPG Maker MV/MZ：优先走 WebView，不需要 exe 存在 ──────────────
        if (game.engine == GameEngine.RPG_MAKER_MV_MZ) {
            val htmlEntry = listOf(
                File(gameDir, "www/index.html"),
                File(gameDir, "index.html"),
                File(gameDir, "game.html")
            ).firstOrNull { it.exists() && it.isFile }

            if (htmlEntry != null) {
                // 准备初始翻译文件
                ensureTranslationFile(gameDir)
                val webIntent = Intent(context, com.rpgrtl.shell.rpgmaker.RpgMakerWebViewActivity::class.java).apply {
                    putExtra(com.rpgrtl.shell.rpgmaker.RpgMakerWebViewActivity.EXTRA_INDEX_PATH, htmlEntry.absolutePath)
                    putExtra(com.rpgrtl.shell.rpgmaker.RpgMakerWebViewActivity.EXTRA_GAME_DIR, gameDir.absolutePath)
                    putExtra(com.rpgrtl.shell.rpgmaker.RpgMakerWebViewActivity.EXTRA_GAME_TITLE, game.title)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                }
                context.startActivity(webIntent)
                return
            } else {
                Toast.makeText(
                    context,
                    "未找到 RPG Maker 启动页面（www/index.html 或 index.html），请确认游戏目录完整",
                    Toast.LENGTH_LONG
                ).show()
                return
            }
        }

        // ── 其他引擎：需要 exe 文件存在才能走 Wine ───────────────────────
        val exeFile = File(game.executablePath)
        if (!exeFile.exists() || !exeFile.isFile) {
            Toast.makeText(context, "未找到游戏启动文件: ${game.executablePath}", Toast.LENGTH_LONG).show()
            return
        }

        // 启动前检查翻译补丁状态
        ensureTranslationFile(gameDir)

        // Ren'Py 专属实时翻译 Hook 与中文字体热准备
        if (game.engine == GameEngine.RENPY) {
            try {
                val scriptsDir = File(gameDir, "game")
                if (!scriptsDir.exists()) scriptsDir.mkdirs()
                val bridgeFile = File(scriptsDir, "zz_rpgrtl_live_bridge.rpy")
                val source = context.assets.open("renpy/zz_rpgrtl_live_bridge.rpy")
                    .bufferedReader(Charsets.UTF_8).use { it.readText() }
                val old = bridgeFile.takeIf { it.isFile }?.readText(Charsets.UTF_8).orEmpty()
                if (old != source) {
                    bridgeFile.writeText(source, Charsets.UTF_8)
                    File(scriptsDir, "zz_rpgrtl_live_bridge.rpyc").delete()
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        // 构建 Winlator WineDisplayActivity 启动意图
        val intent = Intent(context, WineDisplayActivity::class.java).apply {
            putExtra(WineDisplayActivity.EXTRA_GAME_URI, game.executablePath)
            putExtra(WineDisplayActivity.EXTRA_GAME_TITLE, game.title)
            putExtra(WineDisplayActivity.EXTRA_CONTAINER_ID, 1)
            putExtra(WineDisplayActivity.EXTRA_BOX64_PRESET, containerConfig?.box64Preset ?: game.box64Preset)
            putExtra(WineDisplayActivity.EXTRA_GRAPHICS_DRIVER, containerConfig?.graphicsDriver ?: game.graphicsDriver)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }

        context.startActivity(intent)
    }

    private fun ensureTranslationFile(gameDir: File) {
        try {
            val initialFile = File(gameDir, "翻译文件.json")
            if (!initialFile.exists()) {
                initialFile.writeText("{}", Charsets.UTF_8)
            }
        } catch (_: Exception) {}
    }

    /**
     * 引擎补丁建议与环境提示
     */
    fun getEngineAdvice(engine: GameEngine): String {
        return when (engine) {
            GameEngine.RPG_MAKER_MV_MZ -> "已自动适配 NW.js 注入与翻译热重载"
            GameEngine.WOLF_RPG -> "使用 WolfHook 截获文本，支持实时翻译字典注入"
            GameEngine.BAKIN -> "使用 Bakin 专用启动器加载翻译映射"
            GameEngine.RENPY -> "支持 LiveBridge 自动读取 rpyc 文本并替换"
            GameEngine.RPG_MAKER_LEGACY -> "通过 RGSSHook 挂钩 Ruby 脚本并加载中文字体"
            GameEngine.TYRANO -> "通过 TyranoPlugin 替换 scenario 剧本"
            GameEngine.UNITY -> "支持 TextMeshPro / Unity 本地化字典映射"
            GameEngine.CUSTOM -> "通用 PC 游戏，通过 Winlator 运行"
        }
    }
}

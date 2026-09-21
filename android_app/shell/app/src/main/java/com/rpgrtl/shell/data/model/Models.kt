package com.rpgrtl.shell.data.model

import java.io.File

/**
 * 支持的游戏引擎类型
 */
enum class GameEngine(val label: String, val badgeColorHex: Long) {
    RPG_MAKER_MV_MZ("RPG Maker MV/MZ", 0xFF0D9488),
    RPG_MAKER_LEGACY("RPG Maker XP/VX", 0xFF0284C7),
    WOLF_RPG("Wolf RPG Editor", 0xFF7C3AED),
    RENPY("Ren'Py", 0xFFDB2777),
    BAKIN("RPG Developer Bakin", 0xFFD97706),
    TYRANO("TyranoScript", 0xFF4F46E5),
    UNITY("Unity", 0xFF475569),
    CUSTOM("Windows PC Game", 0xFF2563EB);

    companion object {
        fun fromString(value: String): GameEngine {
            val lower = value.lowercase()
            return when {
                lower.contains("mv") || lower.contains("mz") -> RPG_MAKER_MV_MZ
                lower.contains("xp") || lower.contains("vx") || lower.contains("rgss") -> RPG_MAKER_LEGACY
                lower.contains("wolf") -> WOLF_RPG
                lower.contains("ren") -> RENPY
                lower.contains("bakin") -> BAKIN
                lower.contains("tyrano") -> TYRANO
                lower.contains("unity") -> UNITY
                else -> CUSTOM
            }
        }
    }
}

/**
 * 游戏库项
 */
data class GameItem(
    val id: String,
    val title: String,
    val folderPath: String,
    val executablePath: String,
    val engine: GameEngine,
    val iconBase64: String? = null,
    val lastPlayedTime: Long = 0L,
    val translationFileExists: Boolean = false,
    val translatedCount: Int = 0,
    val totalCount: Int = 0,
    val box64Preset: String = "Performance",
    val graphicsDriver: String = "Turnip + DXVK",
    val resolution: String = "1280x720"
) {
    val directory: File
        get() = File(folderPath)

    val executableFile: File
        get() = File(executablePath)

    val translationRatio: Float
        get() = if (totalCount > 0) translatedCount.toFloat() / totalCount.toFloat() else 0f
}

/**
 * 翻译文件单项数据
 */
data class TranslationItem(
    val id: String,
    val source: String,
    var target: String,
    val file: String = "",
    val context: String = "",
    val category: String = "default",
    var hasControlCodeWarning: Boolean = false
)

/**
 * PC 联动连接状态
 */
data class PcConnectionStatus(
    val isConnected: Boolean = false,
    val host: String = "192.168.1.100",
    val port: Int = 35420,
    val pcProjectTitle: String = "",
    val pcProjectEngine: String = "",
    val pcTranslationCount: Int = 0,
    val lastSyncTime: Long = 0L,
    val statusMessage: String = "未连接"
)

/**
 * Winlator 运行容器预设与参数
 */
data class ContainerConfig(
    val name: String = "Default Wine 64-bit",
    val wineVersion: String = "Wine 9.2-x86_64",
    val box64Preset: String = "Performance", // Performance, Compatibility, Safe
    val dxvkVersion: String = "DXVK 2.2",
    val graphicsDriver: String = "Turnip + DXVK",
    val screenResolution: String = "1280x720",
    val driveDPath: String = "", // 映射盘符 D:\
    val enableVirtualControls: Boolean = true,
    val soundDriver: String = "ALSA"
)

/**
 * 游戏修改与作弊器配置
 */
data class TrainerConfig(
    val noclipEnabled: Boolean = false,
    val godModeEnabled: Boolean = false,
    val speedMultiplier: Float = 1.0f,
    val infiniteGold: Boolean = false,
    val customGoldAmount: Long = 999999L,
    val autoRecover: Boolean = false
)

/**
 * 游戏存档位信息
 */
data class GameSaveSlot(
    val id: Int,
    val filename: String,
    val path: String,
    val sizeBytes: Long,
    val lastModified: Long,
    val formattedTime: String = "",
    val detectedGold: Long = -1L
)

package com.rpgrtl.shell.data

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.reflect.TypeToken
import com.rpgrtl.shell.data.model.TranslationItem
import java.io.File
import java.nio.charset.StandardCharsets
import java.util.regex.Pattern

object TranslationManager {
    private val gson: Gson = GsonBuilder().setPrettyPrinting().create()

    private val CONTROL_CODE_PATTERN = Pattern.compile(
        """\\[A-Za-z]+(?:\[[^\]\r\n]{0,128}\])?|\$\{[^}\r\n]{1,160}\}|\{(?:\d+|[A-Za-z_][A-Za-z0-9_.-]{0,80})\}|%(?:\d+\$)?[-+#0 ]*\d*(?:\.\d+)?[diuoxXfFeEgGcs]|<[/!]?[A-Za-z][^>\r\n]{0,160}>|\[\[VAR_[^\]]+\]\]"""
    )

    /**
     * 在游戏目录下寻找主要的翻译字典文件
     */
    fun findTranslationFile(gameDir: File): File? {
        val candidates = listOf(
            File(gameDir, "翻译文件.json"),
            File(gameDir, "game_translation.json"),
            File(gameDir, "ManualTransFile.json"),
            File(gameDir, "translation.json")
        )
        return candidates.firstOrNull { it.isFile && it.exists() }
    }

    /**
     * 获取或创建翻译文件默认路径
     */
    fun getDefaultTranslationFile(gameDir: File): File {
        return findTranslationFile(gameDir) ?: File(gameDir, "翻译文件.json")
    }

    /**
     * 读取翻译文件，转换为 TranslationItem 列表
     */
    fun loadTranslations(file: File): List<TranslationItem> {
        if (!file.exists() || !file.isFile) return emptyList()
        return try {
            val content = file.readText(StandardCharsets.UTF_8).trim()
            if (content.isEmpty()) return emptyList()

            // 格式 1：扁平字典 { "原文": "译文" }
            val mapType = object : TypeToken<Map<String, Any?>>() {}.type
            val rawMap: Map<String, Any?> = gson.fromJson(content, mapType)

            val items = ArrayList<TranslationItem>(rawMap.size)
            var index = 0
            for ((key, value) in rawMap) {
                if (key.isBlank()) continue
                val targetText = value?.toString().orEmpty()
                val warning = checkControlCodeLoss(key, targetText)
                items.add(
                    TranslationItem(
                        id = "trans_${index++}",
                        source = key,
                        target = targetText,
                        category = "default",
                        hasControlCodeWarning = warning
                    )
                )
            }
            items
        } catch (e: Exception) {
            e.printStackTrace()
            emptyList()
        }
    }

    /**
     * 将 TranslationItem 列表保存回标准 翻译文件.json (UTF-8 字典)
     */
    fun saveTranslations(file: File, items: List<TranslationItem>): Boolean {
        return try {
            file.parentFile?.let { parent ->
                if (!parent.exists()) {
                    parent.mkdirs()
                }
            }
            val map = LinkedHashMap<String, String>(items.size)
            for (item in items) {
                if (item.source.isNotBlank()) {
                    map[item.source] = item.target
                }
            }
            val jsonString = gson.toJson(map)
            file.writeText(jsonString, StandardCharsets.UTF_8)
            true
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    /**
     * 提取文本中的控制符和占位符集合
     */
    fun extractControlTokens(text: String): List<String> {
        if (text.isEmpty()) return emptyList()
        val matcher = CONTROL_CODE_PATTERN.matcher(text)
        val tokens = ArrayList<String>()
        while (matcher.find()) {
            tokens.add(matcher.group())
        }
        return tokens
    }

    /**
     * 检测译文是否丢失了原文中的关键控制符号/变量占位符
     */
    fun checkControlCodeLoss(source: String, target: String): Boolean {
        if (target.isBlank()) return false
        val sourceTokens = extractControlTokens(source)
        if (sourceTokens.isEmpty()) return false

        for (token in sourceTokens) {
            if (!target.contains(token)) {
                return true // 丢失了控制符
            }
        }
        return false
    }

    /**
     * 自动修复：若译文丢失控制符，尝试将缺失的控制符补齐或还原
     */
    fun autoRepairControlCodes(source: String, target: String): String {
        val sourceTokens = extractControlTokens(source)
        if (sourceTokens.isEmpty() || target.isBlank()) return target

        var result = target
        for (token in sourceTokens) {
            if (!result.contains(token)) {
                result += " $token"
            }
        }
        return result
    }
}

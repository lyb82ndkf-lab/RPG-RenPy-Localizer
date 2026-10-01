package com.rpgrtl.shell.data

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.gson.stream.JsonReader
import com.rpgrtl.shell.data.model.TranslationItem
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.StringReader
import java.nio.charset.Charset
import java.nio.charset.StandardCharsets
import java.util.regex.Pattern

object TranslationManager {
    private val gson: Gson = GsonBuilder().setPrettyPrinting().create()

    private val CONTROL_CODE_PATTERN = Pattern.compile(
        """\\[A-Za-z]+(?:\[[^\]\r\n]{0,128}\])?|\$\{[^}\r\n]{1,160}\}|\{(?:\d+|[A-Za-z_][A-Za-z0-9_.-]{0,80})\}|%(?:\d+\$)?[-+#0 ]*\d*(?:\.\d+)?[diuoxXfFeEgGcs]|<[/!]?[A-Za-z][^>\r\n]{0,160}>|\[\[VAR_[^\]]+\]\]"""
    )

    private val CANDIDATE_NAMES = listOf(
        "翻译文件.json",
        "ManualTransFile.json",
        "game_translation.json",
        "translation.json",
        "translations.json",
        "RPGRenPyLocalizer_translation.json",
        "live_translation.json",
        "renpy_live_translation.json"
    )

    private val METADATA_KEYS = setOf(
        "version",
        "updated_at",
        "update_at",
        "engine",
        "signature",
        "metadata",
        "author",
        "created_at",
        "tool",
        "config",
        "type",
        "game_title",
        "target_lang",
        "source_lang"
    )

    /**
     * 在游戏目录下寻找主要的翻译字典文件
     * 自动扫描根目录、data、www/data、www、game、.rpgrtl_workspace 等路径
     */
    fun findTranslationFile(gameDir: File): File? {
        if (!gameDir.exists()) return null

        val searchDirs = linkedSetOf<File>()
        searchDirs.add(gameDir)
        searchDirs.add(File(gameDir, "data"))
        searchDirs.add(File(gameDir, "www"))
        searchDirs.add(File(gameDir, "www/data"))
        searchDirs.add(File(gameDir, "game"))
        searchDirs.add(File(gameDir, ".rpgrtl_workspace"))

        gameDir.parentFile?.let { parent ->
            if (parent.exists()) {
                searchDirs.add(parent)
                searchDirs.add(File(parent, "data"))
                searchDirs.add(File(parent, "www/data"))
                searchDirs.add(File(parent, ".rpgrtl_workspace"))
            }
        }

        val allCandidates = mutableListOf<File>()
        for (name in CANDIDATE_NAMES) {
            for (dir in searchDirs) {
                val candidate = File(dir, name)
                if (candidate.isFile && candidate.exists()) {
                    allCandidates.add(candidate)
                }
            }
        }

        // 优先选择非空（有数据内容）的文件
        return allCandidates.firstOrNull { it.length() > 2L } ?: allCandidates.firstOrNull()
    }

    /**
     * 获取或创建翻译文件默认路径
     */
    fun getDefaultTranslationFile(gameDir: File): File {
        return findTranslationFile(gameDir) ?: File(gameDir, "翻译文件.json")
    }

    /**
     * 读取文本并彻底去除 UTF-8 / UTF-16 BOM 头与首尾空白
     */
    fun readCleanText(file: File): String {
        if (!file.exists() || !file.isFile) return ""
        return try {
            val bytes = file.readBytes()
            if (bytes.isEmpty()) return ""

            var offset = 0
            var charset: Charset = StandardCharsets.UTF_8

            if (bytes.size >= 3 &&
                bytes[0] == 0xEF.toByte() &&
                bytes[1] == 0xBB.toByte() &&
                bytes[2] == 0xBF.toByte()
            ) {
                // UTF-8 BOM
                offset = 3
                charset = StandardCharsets.UTF_8
            } else if (bytes.size >= 2 &&
                bytes[0] == 0xFE.toByte() &&
                bytes[1] == 0xFF.toByte()
            ) {
                // UTF-16 BE
                offset = 2
                charset = StandardCharsets.UTF_16BE
            } else if (bytes.size >= 2 &&
                bytes[0] == 0xFF.toByte() &&
                bytes[1] == 0xFE.toByte()
            ) {
                // UTF-16 LE
                offset = 2
                charset = StandardCharsets.UTF_16LE
            }

            var text = String(bytes, offset, bytes.size - offset, charset).trim()
            cleanBomFromString(text)
        } catch (e: Exception) {
            e.printStackTrace()
            ""
        }
    }

    /**
     * 剥除字符串中残留的 BOM 字符
     */
    fun cleanBomFromString(raw: String): String {
        var str = raw.trim()
        while (str.isNotEmpty() && (str[0] == '\uFEFF' || str[0] == '\uFFFE' || str[0] == '\u0000')) {
            str = str.substring(1).trim()
        }
        return str
    }

    /**
     * 读取翻译文件，转换为 TranslationItem 列表
     * 完美兼容各版本导出的扁平字典、嵌套 translations 对象、items/entries 数组等多种格式
     */
    fun loadTranslations(file: File): List<TranslationItem> {
        val content = readCleanText(file)
        if (content.isBlank()) return emptyList()
        return parseTranslations(content)
    }

    /**
     * 健壮解析 JSON 文本为 TranslationItem 列表
     */
    fun parseTranslations(rawContent: String): List<TranslationItem> {
        val clean = cleanBomFromString(rawContent)
        if (clean.isBlank()) return emptyList()

        val result = ArrayList<TranslationItem>()
        val seen = LinkedHashMap<String, TranslationItem>()
        var idIndex = 0

        fun addEntry(source: String, target: String, category: String = "default") {
            val src = source.trim()
            if (src.isEmpty()) return
            val tgt = target.trim()
            val existing = seen[src]
            if (existing == null) {
                val warning = checkControlCodeLoss(src, tgt)
                val item = TranslationItem(
                    id = "trans_${idIndex++}",
                    source = src,
                    target = tgt,
                    category = category,
                    hasControlCodeWarning = warning
                )
                seen[src] = item
                result.add(item)
            } else if (existing.target.isBlank() && tgt.isNotBlank()) {
                val warning = checkControlCodeLoss(src, tgt)
                val updated = existing.copy(target = tgt, hasControlCodeWarning = warning)
                seen[src] = updated
                val idx = result.indexOfFirst { it.source == src }
                if (idx >= 0) {
                    result[idx] = updated
                }
            }
        }

        fun extractFromArray(array: JsonArray, defaultCategory: String = "default") {
            for (i in 0 until array.size()) {
                val el = array.get(i) ?: continue
                if (el.isJsonObject) {
                    val obj = el.asJsonObject
                    val src = obj.get("src")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("source")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("original")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("key")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("id")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: ""
                    val dst = obj.get("dst")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("target")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("translation")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("val")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("text")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: ""
                    val cat = obj.get("category")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: obj.get("type")?.takeIf { it.isJsonPrimitive }?.asString
                        ?: defaultCategory
                    if (src.isNotBlank()) {
                        addEntry(src, dst, cat)
                    }
                }
            }
        }

        fun extractFromObject(obj: JsonObject, parentCategory: String = "default") {
            // 1. 检查是否存在 "translations" 键
            val trans = obj.get("translations")
            if (trans != null) {
                if (trans.isJsonObject) {
                    extractFromObject(trans.asJsonObject, parentCategory)
                    return
                } else if (trans.isJsonArray) {
                    extractFromArray(trans.asJsonArray, parentCategory)
                    return
                }
            }

            // 2. 检查是否存在 "items"、"entries"、"records" 数组
            val items = obj.get("items") ?: obj.get("entries") ?: obj.get("records")
            if (items != null && items.isJsonArray) {
                extractFromArray(items.asJsonArray, parentCategory)
                return
            }

            // 3. 检查是否存在 "data" 嵌套
            val data = obj.get("data")
            if (data != null && data.isJsonObject && !obj.keySet().any { it !in METADATA_KEYS && it != "data" }) {
                extractFromObject(data.asJsonObject, parentCategory)
                return
            }

            // 4. 遍历所有属性
            for ((key, value) in obj.entrySet()) {
                if (key.isBlank() || key in METADATA_KEYS) continue
                when {
                    value.isJsonPrimitive -> {
                        addEntry(key, value.asString, parentCategory)
                    }
                    value.isJsonNull -> {
                        addEntry(key, "", parentCategory)
                    }
                    value.isJsonObject -> {
                        val subObj = value.asJsonObject
                        val dst = subObj.get("target")?.takeIf { it.isJsonPrimitive }?.asString
                            ?: subObj.get("dst")?.takeIf { it.isJsonPrimitive }?.asString
                            ?: subObj.get("text")?.takeIf { it.isJsonPrimitive }?.asString
                            ?: subObj.get("translation")?.takeIf { it.isJsonPrimitive }?.asString
                        if (dst != null) {
                            val cat = subObj.get("category")?.takeIf { it.isJsonPrimitive }?.asString ?: parentCategory
                            addEntry(key, dst, cat)
                        } else {
                            // 子类别分类（例如 "dialogue": { ... }）
                            extractFromObject(subObj, parentCategory = key)
                        }
                    }
                    value.isJsonArray -> {
                        extractFromArray(value.asJsonArray, defaultCategory = key)
                    }
                }
            }
        }

        // 使用宽松模式的 JsonReader 进行解析，可自动兼容注释与逗号容错
        try {
            val reader = JsonReader(StringReader(clean)).apply { isLenient = true }
            val element: JsonElement = JsonParser.parseReader(reader)
            if (element.isJsonObject) {
                extractFromObject(element.asJsonObject)
            } else if (element.isJsonArray) {
                extractFromArray(element.asJsonArray)
            }
        } catch (e: Throwable) {
            // 兜底回退：尝试 org.json 解析
            try {
                if (clean.startsWith("{")) {
                    val root = JSONObject(clean)
                    val mapObj = root.optJSONObject("translations") ?: root.optJSONObject("data") ?: root
                    val keys = mapObj.keys()
                    while (keys.hasNext()) {
                        val k = keys.next()
                        if (k !in METADATA_KEYS && k.isNotBlank()) {
                            val v = when (val opt = mapObj.opt(k)) {
                                is String -> opt
                                is Number, is Boolean -> opt.toString()
                                is JSONObject -> opt.optString("target", opt.optString("text", opt.optString("dst", "")))
                                else -> ""
                            }
                            addEntry(k, v)
                        }
                    }
                } else if (clean.startsWith("[")) {
                    val array = JSONArray(clean)
                    for (i in 0 until array.length()) {
                        val item = array.optJSONObject(i) ?: continue
                        val src = item.optString("src", item.optString("source", item.optString("original", item.optString("key", ""))))
                        val dst = item.optString("dst", item.optString("target", item.optString("translation", item.optString("text", ""))))
                        if (src.isNotBlank()) {
                            addEntry(src, dst)
                        }
                    }
                }
            } catch (_: Throwable) {}
        }

        return result
    }

    /**
     * 将 TranslationItem 列表保存回标准 翻译文件.json (UTF-8 无 BOM 字典)
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
            file.writeBytes(jsonString.toByteArray(StandardCharsets.UTF_8))
            true
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    /**
     * 导出为标准 JSON 字符串
     */
    fun exportToJsonString(items: List<TranslationItem>): String {
        val map = LinkedHashMap<String, String>(items.size)
        for (item in items) {
            if (item.source.isNotBlank()) {
                map[item.source] = item.target
            }
        }
        return gson.toJson(map)
    }

    /**
     * 获取指定游戏目录下的扁平实时翻译字典（原文 -> 译文）
     * 自动包含去除前后空格的备用键以提高游戏内命中率
     */
    fun getTranslationMap(gameDir: File): Map<String, String> {
        val file = findTranslationFile(gameDir) ?: return emptyMap()
        val items = loadTranslations(file)
        val map = LinkedHashMap<String, String>(items.size)
        for (item in items) {
            if (item.source.isNotBlank() && item.target.isNotBlank()) {
                map[item.source] = item.target
                val trimmed = item.source.trim()
                if (trimmed != item.source && !map.containsKey(trimmed)) {
                    map[trimmed] = item.target
                }
            }
        }
        val multilineAdditions = mutableMapOf<String, String>()
        for ((src, tgt) in map) {
            if (src.contains('\n') && tgt.contains('\n')) {
                val sLines = src.split('\n')
                val tLines = tgt.split('\n')
                if (sLines.size == tLines.size) {
                    for (i in sLines.indices) {
                        val sl = sLines[i].trim()
                        val tl = tLines[i].trim()
                        if (sl.isNotEmpty() && tl.isNotEmpty() && !map.containsKey(sl)) {
                            multilineAdditions[sl] = tl
                        }
                    }
                }
            }
        }
        map.putAll(multilineAdditions)
        return map
    }

    /**
     * 获取扁平实时翻译字典的 JSON 字符串，供 WebView / JS 桥接使用
     */
    fun getTranslationMapJson(gameDir: File): String {
        val map = getTranslationMap(gameDir)
        if (map.isEmpty()) return "{}"
        return try {
            val obj = JSONObject()
            for ((k, v) in map) {
                obj.put(k, v)
            }
            obj.toString()
        } catch (_: Exception) {
            gson.toJson(map)
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

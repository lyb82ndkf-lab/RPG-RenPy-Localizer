package com.rpgrtl.shell

import android.content.Context
import androidx.documentfile.provider.DocumentFile
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class AndroidRpgMakerService(
    private val context: Context,
    private val root: DocumentFile
) {
    private val dataDir: DocumentFile = findDataDir(root)
        ?: throw IllegalStateException("未找到 RPG Maker MV/MZ 的 data 目录。")

    fun translationEntries(limit: Int): JSONObject {
        val entries = JSONArray()
        var count = 0
        val seen = mutableSetOf<String>()
        for (file in sortedJsonFiles()) {
            val name = file.name ?: continue
            if (!isTextFile(name)) continue
            val data = readJson(file) ?: continue
            extractTranslations(name, data, mutableListOf(), entries, seen, limit.coerceIn(1, 5000)) { count++ }
        }
        return JSONObject()
            .put("ok", true)
            .put("count", count)
            .put("entries", entries)
    }

    fun dataRecords(category: String, limit: Int): JSONObject {
        val records = JSONArray()
        var count = 0
        for (file in sortedJsonFiles()) {
            val name = file.name ?: continue
            if (!isEditableFile(name)) continue
            if (category.isNotBlank() && category != name && category != categoryFor(name)) continue
            val data = readJson(file) ?: continue
            listRecords(name, data, mutableListOf(), records, limit.coerceIn(1, 5000)) { count++ }
        }
        return JSONObject()
            .put("ok", true)
            .put("count", count)
            .put("records", records)
    }

    fun updateRecord(recordJson: String, newValue: String): JSONObject {
        val record = JSONObject(recordJson)
        val fileName = record.optString("file")
        val path = record.optJSONArray("json_path") ?: throw IllegalArgumentException("记录缺少 json_path。")
        val file = dataDir.findFile(fileName) ?: throw IllegalArgumentException("找不到文件：$fileName")
        val data = readJson(file) ?: throw IllegalArgumentException("无法读取 JSON：$fileName")
        var target: Any = data
        for (index in 0 until path.length() - 1) {
            target = childAt(target, path.get(index))
                ?: throw IllegalArgumentException("路径无效：${record.optString("location")}")
        }
        val last = path.get(path.length() - 1)
        val oldValue = childAt(target, last)
        val coerced = coerceValue(newValue, oldValue)
        setChild(target, last, coerced)
        backupFile(file, "data")
        writeText(file, jsonToString(data))
        return JSONObject()
            .put("ok", true)
            .put("message", "已保存：$fileName / ${record.optString("location")}")
            .put("value", displayValue(coerced))
    }

    fun maps(): JSONObject {
        val info = dataDir.findFile("MapInfos.json")
        val infos = readJson(info) as? JSONArray ?: JSONArray()
        val maps = JSONArray()
        for (index in 0 until infos.length()) {
            val item = infos.optJSONObject(index) ?: continue
            val mapId = item.optInt("id", index)
            val fileName = "Map%03d.json".format(mapId)
            val mapData = readJson(dataDir.findFile(fileName)) as? JSONObject
            val events = mapData?.optJSONArray("events")
            maps.put(
                JSONObject()
                    .put("map_id", mapId)
                    .put("name", item.optString("name", "Map $mapId"))
                    .put("display_name", mapData?.optString("displayName", "") ?: "")
                    .put("file", fileName)
                    .put("width", mapData?.optInt("width", 0) ?: 0)
                    .put("height", mapData?.optInt("height", 0) ?: 0)
                    .put("tileset_id", mapData?.optInt("tilesetId", 0) ?: 0)
                    .put("event_count", countNonNull(events))
            )
        }
        return JSONObject().put("ok", true).put("count", maps.length()).put("maps", maps)
    }

    fun mapDetail(mapId: Int): JSONObject {
        val maps = maps().optJSONArray("maps") ?: JSONArray()
        var record = JSONObject()
        for (index in 0 until maps.length()) {
            val item = maps.optJSONObject(index) ?: continue
            if (item.optInt("map_id") == mapId) {
                record = item
                break
            }
        }
        if (record.length() == 0) {
            record = JSONObject()
                .put("map_id", mapId)
                .put("name", "Map $mapId")
                .put("display_name", "")
                .put("file", "Map%03d.json".format(mapId))
                .put("width", 0)
                .put("height", 0)
                .put("tileset_id", 0)
                .put("event_count", 0)
        }
        val data = readJson(dataDir.findFile(record.optString("file"))) as? JSONObject ?: JSONObject()
        val width = data.optInt("width", record.optInt("width", 0))
        val height = data.optInt("height", record.optInt("height", 0))
        val tilesetId = data.optInt("tilesetId", record.optInt("tileset_id", 0))
        val passable = mapPassability(data, width, height, tilesetId)
        val events = mapEvents(data)
        val eventCounts = mutableMapOf<Pair<Int, Int>, Int>()
        val transferCounts = mutableMapOf<Pair<Int, Int>, Int>()
        for (index in 0 until events.length()) {
            val ev = events.optJSONObject(index) ?: continue
            val key = ev.optInt("x") to ev.optInt("y")
            eventCounts[key] = (eventCounts[key] ?: 0) + 1
            val transfers = ev.optJSONArray("transfers")
            if (transfers != null && transfers.length() > 0) {
                transferCounts[key] = (transferCounts[key] ?: 0) + transfers.length()
            }
        }
        val tiles = JSONArray()
        for (y in 0 until height) {
            for (x in 0 until width) {
                val key = x to y
                tiles.put(
                    JSONObject()
                        .put("x", x)
                        .put("y", y)
                        .put("passable", passable[key] ?: true)
                        .put("event_count", eventCounts[key] ?: 0)
                        .put("transfer_count", transferCounts[key] ?: 0)
                )
            }
        }
        record.put("width", width).put("height", height).put("tileset_id", tilesetId).put("event_count", events.length())
        return JSONObject()
            .put("ok", true)
            .put("detail", JSONObject().put("record", record).put("tiles", tiles).put("events", events))
    }

    fun saveSlots(): JSONObject {
        val saveDir = root.findFile("save")
        val slots = JSONArray()
        if (saveDir != null && saveDir.isDirectory) {
            for (file in saveDir.listFiles().sortedBy { it.name ?: "" }) {
                val name = file.name ?: continue
                val match = Regex("""file(\d+)\.(rpgsave|rmmzsave)""", RegexOption.IGNORE_CASE).matchEntire(name) ?: continue
                slots.put(
                    JSONObject()
                        .put("slot_id", match.groupValues[1].toInt())
                        .put("label", "存档 ${match.groupValues[1]}")
                        .put("name", name)
                        .put("size", file.length())
                        .put("modified_at", formatTime(file.lastModified()))
                )
            }
        }
        return JSONObject().put("ok", true).put("count", slots.length()).put("slots", slots)
    }

    fun createSaveBackup(): JSONObject {
        val saveDir = root.findFile("save") ?: throw IllegalStateException("没有找到 save 目录。")
        val backupDir = ensureDir(ensureDir(ensureDir(root, ".rpgrtl_android"), "backup"), "save")
        var copied = 0
        for (file in saveDir.listFiles()) {
            val name = file.name ?: continue
            if (!Regex("""file\d+\.(rpgsave|rmmzsave)""", RegexOption.IGNORE_CASE).matches(name)) continue
            copyFile(file, backupDir, "$name.${stamp()}.bak")
            copied += 1
        }
        return JSONObject().put("ok", true).put("message", "已备份 $copied 个存档到 .rpgrtl_android/backup/save").put("count", copied)
    }

    fun backups(): JSONObject {
        val backupRoot = root.findFile(".rpgrtl_android")?.findFile("backup")
        val items = JSONArray()
        fun walk(dir: DocumentFile?, prefix: String) {
            if (dir == null || !dir.isDirectory) return
            for (file in dir.listFiles().sortedByDescending { it.lastModified() }) {
                val name = file.name ?: continue
                val path = if (prefix.isBlank()) name else "$prefix/$name"
                if (file.isDirectory) walk(file, path) else items.put(
                    JSONObject()
                        .put("name", name)
                        .put("path", path)
                        .put("size", file.length())
                        .put("modified_at", formatTime(file.lastModified()))
                )
            }
        }
        walk(backupRoot, "")
        return JSONObject().put("ok", true).put("count", items.length()).put("backups", items)
    }

    private fun sortedJsonFiles(): List<DocumentFile> {
        return dataDir.listFiles()
            .filter { it.isFile && (it.name ?: "").endsWith(".json", ignoreCase = true) }
            .sortedBy { it.name ?: "" }
    }

    private fun extractTranslations(
        fileName: String,
        node: Any,
        path: MutableList<Any>,
        out: JSONArray,
        seen: MutableSet<String>,
        limit: Int,
        inc: () -> Unit
    ) {
        if (node is JSONObject) {
            if (node.has("code") && node.has("parameters")) {
                extractEventCommand(fileName, node, path, out, seen, limit, inc)
            }
            val keys = node.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                val value = node.opt(key)
                if (key in TRANSLATABLE_KEYS && value is String && value.isNotBlank()) {
                    addTranslation(fileName, path + key, value, fileName, path.joinToString(" / "), translationCategory(fileName, key), out, seen, limit, inc)
                }
                if (value is JSONObject || value is JSONArray) {
                    path.add(key)
                    extractTranslations(fileName, value, path, out, seen, limit, inc)
                    path.removeAt(path.lastIndex)
                }
            }
        } else if (node is JSONArray) {
            for (index in 0 until node.length()) {
                val value = node.opt(index)
                if (value is JSONObject || value is JSONArray) {
                    path.add(index)
                    extractTranslations(fileName, value, path, out, seen, limit, inc)
                    path.removeAt(path.lastIndex)
                }
            }
        }
    }

    private fun extractEventCommand(
        fileName: String,
        command: JSONObject,
        path: List<Any>,
        out: JSONArray,
        seen: MutableSet<String>,
        limit: Int,
        inc: () -> Unit
    ) {
        val code = command.optInt("code", 0)
        val params = command.optJSONArray("parameters") ?: return
        fun add(paramPath: List<Any>, text: String) {
            addTranslation(fileName, path + "parameters" + paramPath, text, fileName, "event code $code", eventCategory(code), out, seen, limit, inc)
        }
        if (code in setOf(401, 405, 355, 655) && params.opt(0) is String) add(listOf(0), params.optString(0))
        if (code == 101 && params.opt(4) is String) add(listOf(4), params.optString(4))
        if (code == 102 && params.opt(0) is JSONArray) {
            val options = params.optJSONArray(0) ?: return
            for (index in 0 until options.length()) {
                val text = options.opt(index)
                if (text is String) add(listOf(0, index), text)
            }
        }
        if (code == 402 && params.opt(1) is String) add(listOf(1), params.optString(1))
        if (code == 122 && params.opt(4) is String) {
            val raw = params.optString(4)
            if ((raw.startsWith("'") && raw.endsWith("'")) || (raw.startsWith("\"") && raw.endsWith("\""))) {
                add(listOf(4), raw.substring(1, raw.length - 1))
            }
        }
    }

    private fun addTranslation(
        fileName: String,
        path: List<Any>,
        source: String,
        file: String,
        context: String,
        category: String,
        out: JSONArray,
        seen: MutableSet<String>,
        limit: Int,
        inc: () -> Unit
    ) {
        if (source.isBlank()) return
        val id = makeId(fileName, path)
        if (!seen.add(id)) return
        inc()
        if (out.length() >= limit) return
        out.put(
            JSONObject()
                .put("entry_id", id)
                .put("source", source)
                .put("target", "")
                .put("file", file)
                .put("context", context)
                .put("category", category)
        )
    }

    private fun listRecords(
        fileName: String,
        node: Any,
        path: MutableList<Any>,
        out: JSONArray,
        limit: Int,
        inc: () -> Unit
    ) {
        if (node is JSONObject) {
            val keys = node.keys()
            while (keys.hasNext()) {
                val key = keys.next()
                if (key in SKIP_DATA_KEYS) continue
                val value = node.opt(key)
                val nextPath = path + key
                if (isScalar(value)) addRecord(fileName, nextPath, value, out, limit, inc)
                if (value is JSONObject || value is JSONArray) {
                    path.add(key)
                    listRecords(fileName, value, path, out, limit, inc)
                    path.removeAt(path.lastIndex)
                }
            }
        } else if (node is JSONArray) {
            for (index in 0 until node.length()) {
                val value = node.opt(index) ?: continue
                val nextPath = path + index
                if (isScalar(value)) addRecord(fileName, nextPath, value, out, limit, inc)
                if (value is JSONObject || value is JSONArray) {
                    path.add(index)
                    listRecords(fileName, value, path, out, limit, inc)
                    path.removeAt(path.lastIndex)
                }
            }
        }
    }

    private fun addRecord(fileName: String, path: List<Any>, value: Any?, out: JSONArray, limit: Int, inc: () -> Unit) {
        if (value is String && value.isBlank()) return
        inc()
        if (out.length() >= limit) return
        out.put(
            JSONObject()
                .put("record_id", makeId(fileName, path))
                .put("label", path.drop(if (path.firstOrNull() is Int) 1 else 0).joinToString(" / "))
                .put("value", displayValue(value))
                .put("file", fileName)
                .put("category", categoryFor(fileName))
                .put("object_id", objectId(fileName, path))
                .put("object_label", objectLabel(fileName, path))
                .put("location", path.joinToString("/"))
                .put("json_path", JSONArray(path))
        )
    }

    private fun mapPassability(data: JSONObject, width: Int, height: Int, tilesetId: Int): Map<Pair<Int, Int>, Boolean> {
        val tilesets = readJson(dataDir.findFile("Tilesets.json")) as? JSONArray ?: JSONArray()
        val flags = tilesets.optJSONObject(tilesetId)?.optJSONArray("flags") ?: JSONArray()
        val raw = data.optJSONArray("data") ?: JSONArray()
        val result = mutableMapOf<Pair<Int, Int>, Boolean>()
        val layerCount = if (width * height > 0) (raw.length() / (width * height)).coerceAtLeast(1).coerceAtMost(6) else 1
        for (y in 0 until height) {
            for (x in 0 until width) {
                var blocked = false
                for (z in 0 until layerCount) {
                    val index = (z * height + y) * width + x
                    val tileId = raw.optInt(index, 0)
                    if (tileId <= 0 || tileId >= flags.length()) continue
                    val flag = flags.optInt(tileId, 0)
                    if (flag and 0x10 != 0) continue
                    if (flag and 0x0F == 0x0F) {
                        blocked = true
                        break
                    }
                }
                result[x to y] = !blocked
            }
        }
        return result
    }

    private fun mapEvents(data: JSONObject): JSONArray {
        val result = JSONArray()
        val events = data.optJSONArray("events") ?: return result
        for (fallbackId in 0 until events.length()) {
            val raw = events.optJSONObject(fallbackId) ?: continue
            val pages = raw.optJSONArray("pages") ?: JSONArray()
            val conditions = JSONArray()
            val transfers = JSONArray()
            val commandsSummary = JSONArray()
            var commandCount = 0
            for (pageIndex in 0 until pages.length()) {
                val page = pages.optJSONObject(pageIndex) ?: continue
                eventPageConditions(pageIndex + 1, page.optJSONObject("conditions") ?: JSONObject(), conditions)
                val commands = page.optJSONArray("list") ?: JSONArray()
                commandCount += commands.length()
                eventCommandSummary(commands, commandsSummary, transfers)
            }
            val eventId = raw.optInt("id", fallbackId)
            result.put(
                JSONObject()
                    .put("event_id", eventId)
                    .put("name", raw.optString("name", "Event $eventId"))
                    .put("x", raw.optInt("x", 0))
                    .put("y", raw.optInt("y", 0))
                    .put("page_count", pages.length())
                    .put("command_count", commandCount)
                    .put("conditions", conditions)
                    .put("transfers", transfers)
                    .put("commands", commandsSummary)
            )
        }
        return result
    }

    private fun eventPageConditions(pageIndex: Int, conditions: JSONObject, out: JSONArray) {
        var added = false
        if (conditions.optBoolean("switch1Valid")) { out.put("页$pageIndex: 开关 ${conditions.optInt("switch1Id")} ON"); added = true }
        if (conditions.optBoolean("switch2Valid")) { out.put("页$pageIndex: 开关 ${conditions.optInt("switch2Id")} ON"); added = true }
        if (conditions.optBoolean("variableValid")) { out.put("页$pageIndex: 变量 ${conditions.optInt("variableId")} >= ${conditions.opt("variableValue")}"); added = true }
        if (conditions.optBoolean("selfSwitchValid")) { out.put("页$pageIndex: 独立开关 ${conditions.optString("selfSwitchCh")} ON"); added = true }
        if (conditions.optBoolean("itemValid")) { out.put("页$pageIndex: 持有物品 ${conditions.optInt("itemId")}"); added = true }
        if (conditions.optBoolean("actorValid")) { out.put("页$pageIndex: 队伍含角色 ${conditions.optInt("actorId")}"); added = true }
        if (!added) out.put("页$pageIndex: 无触发条件")
    }

    private fun eventCommandSummary(commands: JSONArray, summary: JSONArray, transfers: JSONArray) {
        for (index in 0 until commands.length()) {
            val command = commands.optJSONObject(index) ?: continue
            val code = command.optInt("code", 0)
            val params = command.optJSONArray("parameters") ?: JSONArray()
            when {
                code == 401 && params.opt(0) is String -> summary.put("对话：${params.optString(0).take(32)}")
                code == 405 && params.opt(0) is String -> summary.put("滚动文本：${params.optString(0).take(32)}")
                code == 121 && params.length() >= 3 -> summary.put("开关：${params.opt(0)}-${params.opt(1)}")
                code == 122 && params.length() >= 5 -> summary.put("变量：${params.opt(0)}-${params.opt(1)}")
                code == 201 && params.length() >= 5 -> {
                    val text = "传送：地图 ${params.opt(1)} (${params.opt(2)}, ${params.opt(3)})"
                    summary.put(text)
                    transfers.put(text)
                }
                code == 355 -> summary.put("脚本")
            }
        }
    }

    private fun readJson(file: DocumentFile?): Any? {
        if (file == null || !file.isFile) return null
        val text = readText(file)
        return try {
            JSONObject(text)
        } catch (_: Throwable) {
            try { JSONArray(text) } catch (_: Throwable) { null }
        }
    }

    private fun readText(file: DocumentFile): String {
        return context.contentResolver.openInputStream(file.uri)?.use { input ->
            input.readBytes().toString(Charsets.UTF_8)
        } ?: ""
    }

    private fun jsonToString(value: Any): String {
        return when (value) {
            is JSONObject -> value.toString(2)
            is JSONArray -> value.toString(2)
            else -> value.toString()
        }
    }

    private fun writeText(file: DocumentFile, text: String) {
        context.contentResolver.openOutputStream(file.uri, "wt")?.use { output ->
            output.write(text.toByteArray(Charsets.UTF_8))
        } ?: throw IllegalStateException("无法写入文件：${file.name}")
    }

    private fun backupFile(file: DocumentFile, group: String) {
        val backupDir = ensureDir(ensureDir(ensureDir(root, ".rpgrtl_android"), "backup"), group)
        copyFile(file, backupDir, "${file.name}.${stamp()}.bak")
    }

    private fun copyFile(source: DocumentFile, targetDir: DocumentFile, targetName: String) {
        val target = targetDir.createFile("application/octet-stream", targetName)
            ?: throw IllegalStateException("无法创建备份文件：$targetName")
        context.contentResolver.openInputStream(source.uri)?.use { input ->
            context.contentResolver.openOutputStream(target.uri, "wt")?.use { output ->
                input.copyTo(output)
            }
        }
    }

    private fun ensureDir(parent: DocumentFile, name: String): DocumentFile {
        parent.findFile(name)?.let {
            if (it.isDirectory) return it
        }
        return parent.createDirectory(name) ?: throw IllegalStateException("无法创建目录：$name")
    }

    private fun childAt(target: Any, key: Any): Any? {
        return when (target) {
            is JSONObject -> target.opt(key.toString())
            is JSONArray -> target.opt((key as Number).toInt())
            else -> null
        }
    }

    private fun setChild(target: Any, key: Any, value: Any?) {
        when (target) {
            is JSONObject -> target.put(key.toString(), value)
            is JSONArray -> target.put((key as Number).toInt(), value)
        }
    }

    private fun coerceValue(value: String, old: Any?): Any? {
        val text = value.trim()
        return when (old) {
            is Boolean -> text.lowercase() in setOf("1", "true", "yes", "y", "on", "是")
            is Int -> text.toInt()
            is Long -> text.toLong()
            is Double -> text.toDouble()
            JSONObject.NULL, null -> if (text.lowercase() == "null") JSONObject.NULL else value
            else -> value
        }
    }

    private fun displayValue(value: Any?): String {
        return when (value) {
            null, JSONObject.NULL -> "null"
            is Boolean -> if (value) "true" else "false"
            else -> value.toString()
        }
    }

    private fun isScalar(value: Any?): Boolean {
        return value == null || value == JSONObject.NULL || value is String || value is Number || value is Boolean
    }

    private fun makeId(fileName: String, path: List<Any>): String = "$fileName::" + path.joinToString("/")

    private fun objectId(fileName: String, path: List<Any>): String {
        return if (path.firstOrNull() is Int) "$fileName:${path.first()}" else "$fileName:root"
    }

    private fun objectLabel(fileName: String, path: List<Any>): String {
        val base = fileName.removeSuffix(".json")
        return if (path.firstOrNull() is Int) "$base ${path.first()}" else base
    }

    private fun isTextFile(name: String): Boolean = name in TEXT_FILES || (name.startsWith("Map") && name.endsWith(".json"))

    private fun isEditableFile(name: String): Boolean = name in EDITABLE_DB_FILES || (name.startsWith("Map") && name.endsWith(".json"))

    private fun categoryFor(fileName: String): String {
        return when {
            fileName == "MapInfos.json" -> "MapInfos 地图"
            fileName.startsWith("Map") && fileName.endsWith(".json") -> "Maps 地图事件"
            else -> CATEGORY_LABELS[fileName] ?: fileName.removeSuffix(".json")
        }
    }

    private fun translationCategory(fileName: String, key: String): String {
        return when {
            fileName == "System.json" -> "system"
            fileName.startsWith("Map") || fileName == "CommonEvents.json" -> "dialogue"
            key == "displayName" -> "event"
            else -> "database"
        }
    }

    private fun eventCategory(code: Int): String = if (code in setOf(401, 405, 101, 102, 402, 403)) "dialogue" else "event"

    private fun countNonNull(array: JSONArray?): Int {
        if (array == null) return 0
        var count = 0
        for (index in 0 until array.length()) if (!array.isNull(index)) count += 1
        return count
    }

    private fun formatTime(value: Long): String {
        if (value <= 0) return ""
        return SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date(value))
    }

    private fun stamp(): String = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())

    companion object {
        private val TEXT_FILES = setOf(
            "Actors.json", "Armors.json", "Classes.json", "Enemies.json", "Items.json",
            "MapInfos.json", "Skills.json", "States.json", "Weapons.json", "System.json", "CommonEvents.json"
        )
        private val EDITABLE_DB_FILES = setOf(
            "Actors.json", "Armors.json", "Classes.json", "Enemies.json", "Items.json",
            "Skills.json", "States.json", "Weapons.json", "System.json", "MapInfos.json", "CommonEvents.json"
        )
        private val TRANSLATABLE_KEYS = setOf(
            "name", "description", "profile", "nickname", "message1", "message2",
            "message3", "message4", "displayName", "gameTitle", "currencyUnit"
        )
        private val SKIP_DATA_KEYS = setOf("note", "traits", "effects")
        private val CATEGORY_LABELS = mapOf(
            "Actors.json" to "角色",
            "Armors.json" to "防具",
            "Classes.json" to "职业",
            "Enemies.json" to "敌人",
            "Items.json" to "物品",
            "Skills.json" to "技能",
            "States.json" to "状态",
            "Weapons.json" to "武器",
            "System.json" to "系统",
            "CommonEvents.json" to "公共事件"
        )

        private fun findDataDir(root: DocumentFile): DocumentFile? {
            root.findFile("www")?.findFile("data")?.let { if (it.isDirectory) return it }
            root.findFile("data")?.let { if (it.isDirectory) return it }
            fun walk(node: DocumentFile, depth: Int): DocumentFile? {
                if (depth > 4) return null
                for (child in node.listFiles()) {
                    if (!child.isDirectory) continue
                    if (child.name.equals("data", ignoreCase = true) && child.findFile("System.json") != null) return child
                    walk(child, depth + 1)?.let { return it }
                }
                return null
            }
            return walk(root, 0)
        }
    }
}

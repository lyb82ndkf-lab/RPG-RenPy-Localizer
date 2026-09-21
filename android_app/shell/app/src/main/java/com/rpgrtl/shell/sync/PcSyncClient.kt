package com.rpgrtl.shell.sync

import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.reflect.TypeToken
import com.rpgrtl.shell.data.TranslationManager
import com.rpgrtl.shell.data.model.PcConnectionStatus
import com.rpgrtl.shell.data.model.TranslationItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.util.concurrent.TimeUnit

class PcSyncClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    /**
     * 测试并连接 PC 端 RPGRenPyLocalizer 服务
     */
    suspend fun checkConnection(host: String, port: Int): Result<PcConnectionStatus> = withContext(Dispatchers.IO) {
        val url = "http://$host:$port/api/project/summary"
        try {
            val request = Request.Builder()
                .url(url)
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return@withContext Result.failure(Exception("HTTP ${response.code}: ${response.message}"))
                }
                val body = response.body?.string().orEmpty()
                val json = gson.fromJson(body, JsonObject::class.java)

                val engine = json.get("engine")?.asString.orEmpty()
                val root = json.get("root")?.asString.orEmpty()
                val count = json.get("translationCount")?.asInt ?: 0
                val title = if (root.isNotBlank()) File(root).name else "PC Game"

                Result.success(
                    PcConnectionStatus(
                        isConnected = true,
                        host = host,
                        port = port,
                        pcProjectTitle = title,
                        pcProjectEngine = engine,
                        pcTranslationCount = count,
                        lastSyncTime = System.currentTimeMillis(),
                        statusMessage = "连接成功 · $engine"
                    )
                )
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 从 PC 端拉取完整翻译条目并保存到本地文件
     */
    suspend fun pullTranslationsFromPc(
        host: String,
        port: Int,
        destFile: File
    ): Result<List<TranslationItem>> = withContext(Dispatchers.IO) {
        val url = "http://$host:$port/api/translations?all=1"
        try {
            val request = Request.Builder()
                .url(url)
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return@withContext Result.failure(Exception("HTTP ${response.code}: ${response.message}"))
                }
                val body = response.body?.string().orEmpty()
                val json = gson.fromJson(body, JsonObject::class.java)
                val entriesArray = json.getAsJsonArray("entries") ?: JsonArray()

                val items = ArrayList<TranslationItem>(entriesArray.size())
                var idx = 0
                for (elem in entriesArray) {
                    val obj = elem.asJsonObject
                    val id = obj.get("entry_id")?.asString ?: "pc_${idx++}"
                    val source = obj.get("source")?.asString.orEmpty()
                    val target = obj.get("target")?.asString.orEmpty()
                    val file = obj.get("file")?.asString.orEmpty()
                    val context = obj.get("context")?.asString.orEmpty()
                    val category = obj.get("category")?.asString ?: "default"

                    val warning = TranslationManager.checkControlCodeLoss(source, target)
                    items.add(
                        TranslationItem(
                            id = id,
                            source = source,
                            target = target,
                            file = file,
                            context = context,
                            category = category,
                            hasControlCodeWarning = warning
                        )
                    )
                }

                // 立即将拉取的条目写入本地游戏目录的 翻译文件.json
                TranslationManager.saveTranslations(destFile, items)
                Result.success(items)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 将手机端已修改的翻译条目推送到 PC 端
     */
    suspend fun pushTranslationsToPc(
        host: String,
        port: Int,
        items: List<TranslationItem>
    ): Result<Int> = withContext(Dispatchers.IO) {
        val url = "http://$host:$port/api/translations/save-targets"
        try {
            val payload = JsonObject()
            val updates = JsonArray()

            for (item in items) {
                if (item.target.isNotBlank()) {
                    val entryObj = JsonObject()
                    entryObj.addProperty("entry_id", item.id)
                    entryObj.addProperty("source", item.source)
                    entryObj.addProperty("target", item.target)
                    entryObj.addProperty("file", item.file)
                    entryObj.addProperty("context", item.context)
                    entryObj.addProperty("category", item.category)
                    updates.add(entryObj)
                }
            }
            payload.add("updates", updates)
            payload.addProperty("allowPartial", true)

            val body = payload.toString().toRequestBody(jsonMediaType)
            val request = Request.Builder()
                .url(url)
                .post(body)
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return@withContext Result.failure(Exception("HTTP ${response.code}: ${response.message}"))
                }
                val respBody = response.body?.string().orEmpty()
                val json = gson.fromJson(respBody, JsonObject::class.java)
                val changed = json.get("changed")?.asInt ?: updates.size()
                Result.success(changed)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 触发 PC 端生成即玩补丁
     */
    suspend fun requestPcGeneratePatch(
        host: String,
        port: Int,
        targetDir: String
    ): Result<String> = withContext(Dispatchers.IO) {
        val url = "http://$host:$port/api/cold/generate-mtool-patch"
        try {
            val payload = JsonObject()
            payload.addProperty("targetDir", targetDir)

            val body = payload.toString().toRequestBody(jsonMediaType)
            val request = Request.Builder()
                .url(url)
                .post(body)
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return@withContext Result.failure(Exception("HTTP ${response.code}: ${response.message}"))
                }
                val respBody = response.body?.string().orEmpty()
                Result.success(respBody)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

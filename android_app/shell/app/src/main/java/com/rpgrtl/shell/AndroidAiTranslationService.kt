package com.rpgrtl.shell

import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class AndroidAiTranslationService {
    fun translate(request: JSONObject): JSONObject {
        return try {
            translateUnsafe(request)
        } catch (error: Throwable) {
            JSONObject()
                .put("ok", false)
                .put("error", error.message ?: error.javaClass.simpleName)
        }
    }

    private fun translateUnsafe(request: JSONObject): JSONObject {
        val settings = request.optJSONObject("settings") ?: JSONObject()
        val entries = request.optJSONArray("entries") ?: JSONArray()
        if (entries.length() == 0) {
            return JSONObject()
                .put("ok", true)
                .put("translations", JSONArray())
                .put("message", "No entries to translate.")
        }

        val provider = settings.optString("provider", "deepseek").lowercase()
        val apiKey = settings.optString("apiKey", "").trim()
        if (apiKey.isBlank()) {
            throw IllegalArgumentException("API Key is empty.")
        }

        val model = settings.optString("model", defaultModel(provider)).ifBlank { defaultModel(provider) }
        val baseUrl = resolveBaseUrl(provider, settings)
        val endpoint = chatCompletionsUrl(baseUrl)
        val keyByNumber = mutableMapOf<String, String>()
        val sourceByEntryId = mutableMapOf<String, String>()
        val sourcePayload = JSONObject()

        val maxEntries = minOf(entries.length(), 120)
        for (i in 0 until maxEntries) {
            val entry = entries.optJSONObject(i) ?: continue
            val source = entry.optString("source", "").trim()
            val entryId = entry.optString("entry_id", "")
            if (source.isBlank() || entryId.isBlank()) continue
            val number = (keyByNumber.size + 1).toString()
            keyByNumber[number] = entryId
            sourceByEntryId[entryId] = source
            sourcePayload.put(number, source)
        }
        if (keyByNumber.isEmpty()) {
            return JSONObject().put("ok", true).put("translations", JSONArray())
        }

        val messages = JSONArray()
            .put(
                JSONObject()
                    .put("role", "system")
                    .put(
                        "content",
                        "You are a professional game localization translator. Translate Japanese or English game dialogue, item names, UI text, and descriptions into Simplified Chinese. Keep RPG control codes, variables, file names, paths, tags, and placeholders unchanged. If a value is already Simplified Chinese, return it unchanged. Return only a valid JSON object whose keys match the input keys."
                    )
            )
            .put(
                JSONObject()
                    .put("role", "user")
                    .put(
                        "content",
                        "Translate the values of this JSON object into Simplified Chinese. Return only JSON, no markdown:\n$sourcePayload"
                    )
            )

        val payload = JSONObject()
            .put("model", model)
            .put("messages", messages)
            .put("temperature", settings.optDouble("temperature", 0.2))
            .put("top_p", settings.optDouble("top_p", 0.9))
            .put("max_tokens", settings.optInt("max_tokens", 8192))

        val raw = postJson(endpoint, provider, apiKey, payload)
        val content = JSONObject(raw)
            .optJSONArray("choices")
            ?.optJSONObject(0)
            ?.optJSONObject("message")
            ?.optString("content", "")
            ?: throw IllegalStateException("AI response has no message content.")
        val translatedObject = parseTranslatedObject(extractJsonObject(content))
        val translations = JSONArray()
        for ((number, entryId) in keyByNumber) {
            val source = sourceByEntryId[entryId] ?: ""
            val zeroBased = (number.toIntOrNull()?.minus(1))?.toString().orEmpty()
            val target = when {
                translatedObject.has(number) -> translatedObject.optString(number, "")
                translatedObject.has(zeroBased) -> translatedObject.optString(zeroBased, "")
                translatedObject.has(entryId) -> translatedObject.optString(entryId, "")
                translatedObject.has(source) -> translatedObject.optString(source, "")
                else -> ""
            }.trim()
            if (target.isBlank()) continue
            translations.put(
                JSONObject()
                    .put("entry_id", entryId)
                    .put("source", source)
                    .put("target", target)
            )
        }

        return JSONObject()
            .put("ok", true)
            .put("provider", provider)
            .put("model", model)
            .put("count", translations.length())
            .put("translations", translations)
    }

    private fun postJson(endpoint: String, provider: String, apiKey: String, payload: JSONObject): String {
        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 45000
            readTimeout = 120000
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", "application/json")
            if (provider == "xiaomi_token_plan") {
                setRequestProperty("api-key", apiKey)
            } else {
                setRequestProperty("Authorization", "Bearer $apiKey")
            }
        }
        OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
            writer.write(payload.toString())
        }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val body = BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { it.readText() }
        if (status !in 200..299) {
            throw IllegalStateException("AI API HTTP $status: ${body.take(700)}")
        }
        return body
    }

    private fun resolveBaseUrl(provider: String, settings: JSONObject): String {
        val custom = settings.optString("baseUrl", "").trim().trimEnd('/')
        if (custom.isNotBlank()) return custom
        return when (provider) {
            "deepseek" -> "https://api.deepseek.com"
            "doubao" -> "https://ark.cn-beijing.volces.com/api/v3"
            "glm" -> "https://open.bigmodel.cn/api/paas/v4"
            "nvidia" -> "https://integrate.api.nvidia.com/v1"
            "xiaomi_token_plan" -> {
                when (settings.optString("cluster", "sgp").lowercase()) {
                    "cn" -> "https://token-plan-cn.xiaomimimo.com/v1"
                    "ams", "eu", "europe" -> "https://token-plan-ams.xiaomimimo.com/v1"
                    else -> "https://token-plan-sgp.xiaomimimo.com/v1"
                }
            }
            else -> "https://api.openai.com/v1"
        }
    }

    private fun chatCompletionsUrl(baseUrl: String): String {
        val base = baseUrl.trim().trimEnd('/')
        return if (base.endsWith("/chat/completions")) base else "$base/chat/completions"
    }

    private fun defaultModel(provider: String): String {
        return when (provider) {
            "deepseek" -> "deepseek-chat"
            "doubao" -> "doubao-seed-2-0-mini-250715"
            "glm" -> "glm-4-flash"
            "nvidia" -> "minimaxai/minimax-m2.7"
            "xiaomi_token_plan" -> "mimo-v2.5"
            else -> "gpt-4o-mini"
        }
    }

    private fun extractJsonObject(content: String): String {
        val cleaned = content
            .trim()
            .removePrefix("```json")
            .removePrefix("```")
            .removeSuffix("```")
            .trim()
        val start = cleaned.indexOf('{')
        val end = cleaned.lastIndexOf('}')
        if (start < 0 || end <= start) {
            throw IllegalStateException("AI response is not JSON: ${cleaned.take(500)}")
        }
        return cleaned.substring(start, end + 1)
    }

    private fun parseTranslatedObject(jsonText: String): JSONObject {
        return try {
            JSONObject(jsonText)
        } catch (first: Throwable) {
            val normalized = jsonText
                .replace('“', '"')
                .replace('”', '"')
                .replace('„', '"')
                .replace('＂', '"')
                .replace('‘', '"')
                .replace('’', '"')
                .replace('：', ':')
                .replace('，', ',')
            try {
                JSONObject(normalized)
            } catch (_: Throwable) {
                throw IllegalStateException("AI returned invalid JSON: ${jsonText.take(700)}")
            }
        }
    }
}

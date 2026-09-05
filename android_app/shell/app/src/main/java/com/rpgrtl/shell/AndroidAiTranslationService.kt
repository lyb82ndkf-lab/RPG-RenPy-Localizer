package com.rpgrtl.shell

import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/** Shared mobile AI adapter: OpenAI-compatible, Anthropic-compatible, and local Ollama. */
class AndroidAiTranslationService {
    fun translate(request: JSONObject): JSONObject = runCatching { translateUnsafe(request) }
        .getOrElse { error(it) }

    fun listModels(settings: JSONObject): JSONObject = runCatching {
        val provider = providerOf(settings)
        val response = request("GET", modelsUrl(provider, settings), provider, apiKey(provider, settings), null)
        val ids = JSONArray()
        val body = JSONObject(response)
        val models = when (provider) {
            PROVIDER_OLLAMA -> body.optJSONArray("models") ?: JSONArray()
            else -> body.optJSONArray("data") ?: JSONArray()
        }
        for (index in 0 until models.length()) {
            val item = models.optJSONObject(index) ?: continue
            val id = if (provider == PROVIDER_OLLAMA) item.optString("name") else item.optString("id")
            if (id.isNotBlank()) ids.put(id)
        }
        if (ids.length() == 0) ids.put(modelOf(provider, settings))
        JSONObject().put("ok", true).put("provider", provider).put("models", ids)
    }.getOrElse { error(it) }

    private fun translateUnsafe(requestJson: JSONObject): JSONObject {
        val settings = requestJson.optJSONObject("settings") ?: JSONObject()
        val entries = requestJson.optJSONArray("entries") ?: JSONArray()
        if (entries.length() == 0) return JSONObject().put("ok", true).put("translations", JSONArray())

        val provider = providerOf(settings)
        val apiKey = apiKey(provider, settings)
        val model = modelOf(provider, settings)
        val sourceByNumber = linkedMapOf<String, Pair<String, String>>()
        val sourcePayload = JSONObject()
        for (index in 0 until minOf(entries.length(), MAX_ENTRIES)) {
            val entry = entries.optJSONObject(index) ?: continue
            val source = entry.optString("source").trim()
            val entryId = entry.optString("entry_id")
            if (source.isBlank() || entryId.isBlank()) continue
            val number = (sourceByNumber.size + 1).toString()
            sourceByNumber[number] = entryId to source
            sourcePayload.put(number, source)
        }
        if (sourceByNumber.isEmpty()) return JSONObject().put("ok", true).put("translations", JSONArray())

        val targetLanguage = requestJson.optString(
            "targetLang",
            settings.optString("targetLang", "Simplified Chinese")
        ).ifBlank { "Simplified Chinese" }
        val system = "You are a professional game localization translator. Translate Japanese or English game dialogue, item names, UI text, and descriptions into $targetLanguage. Keep RPG control codes, variables, file names, paths, tags, and placeholders unchanged and in their original order. If a value is already in $targetLanguage, return it unchanged. Return only a valid JSON object whose keys match the input keys."
        val user = "Translate the values of this JSON object into $targetLanguage. Return only JSON, no markdown:\n$sourcePayload"
        val raw = request("POST", chatUrl(provider, settings), provider, apiKey, chatPayload(provider, model, system, user, settings))
        val translated = parseTranslatedObject(extractJsonObject(responseText(provider, raw)))
        val results = JSONArray()
        sourceByNumber.forEach { (number, pair) ->
            val entryId = pair.first
            val source = pair.second
            val zeroBased = (number.toInt() - 1).toString()
            val target = sequenceOf(number, zeroBased, entryId, source)
                .map { translated.optString(it).trim() }
                .firstOrNull { it.isNotBlank() }
                .orEmpty()
            if (target.isNotBlank()) {
                results.put(JSONObject().put("entry_id", entryId).put("source", source).put("target", target))
            }
        }
        return JSONObject().put("ok", true).put("provider", provider).put("model", model).put("count", results.length()).put("translations", results)
    }

    private fun chatPayload(provider: String, model: String, system: String, user: String, settings: JSONObject): JSONObject {
        val temperature = settings.optDouble("temperature", 0.2)
        val maxTokens = settings.optInt("max_tokens", 8192)
        return when (provider) {
            PROVIDER_ANTHROPIC -> JSONObject()
                .put("model", model).put("max_tokens", maxTokens).put("temperature", temperature)
                .put("system", system)
                .put("messages", JSONArray().put(JSONObject().put("role", "user").put("content", user)))
            PROVIDER_OLLAMA -> JSONObject()
                .put("model", model).put("stream", false)
                .put("messages", messages(system, user))
                .put("options", JSONObject().put("temperature", temperature))
            else -> JSONObject()
                .put("model", model).put("temperature", temperature).put("top_p", settings.optDouble("top_p", 0.9))
                .put("max_tokens", maxTokens).put("messages", messages(system, user))
        }
    }

    private fun messages(system: String, user: String) = JSONArray()
        .put(JSONObject().put("role", "system").put("content", system))
        .put(JSONObject().put("role", "user").put("content", user))

    private fun responseText(provider: String, raw: String): String {
        val body = JSONObject(raw)
        return when (provider) {
            PROVIDER_ANTHROPIC -> body.optJSONArray("content")?.optJSONObject(0)?.optString("text").orEmpty()
            PROVIDER_OLLAMA -> body.optJSONObject("message")?.optString("content").orEmpty()
            else -> body.optJSONArray("choices")?.optJSONObject(0)?.optJSONObject("message")?.optString("content").orEmpty()
        }.ifBlank { throw IllegalStateException("AI response has no text content.") }
    }

    private fun request(method: String, endpoint: String, provider: String, apiKey: String, payload: JSONObject?): String {
        val connection = (URL(endpoint).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            setRequestProperty("Accept", "application/json")
            if (payload != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
            when (provider) {
                PROVIDER_ANTHROPIC -> {
                    setRequestProperty("x-api-key", apiKey)
                    setRequestProperty("anthropic-version", "2023-06-01")
                }
                PROVIDER_OPENAI -> if (apiKey.isNotBlank()) setRequestProperty("Authorization", "Bearer $apiKey")
            }
        }
        if (payload != null) OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { it.write(payload.toString()) }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val body = stream?.let { BufferedReader(InputStreamReader(it, Charsets.UTF_8)).use { reader -> reader.readText() } }.orEmpty()
        if (status !in 200..299) throw IllegalStateException("AI API HTTP $status: ${body.take(700)}")
        return body
    }

    private fun providerOf(settings: JSONObject): String = when (settings.optString("provider").lowercase()) {
        "anthropic", "anthropic_compatible" -> PROVIDER_ANTHROPIC
        "ollama", "ollama_local" -> PROVIDER_OLLAMA
        else -> PROVIDER_OPENAI // preserves legacy DeepSeek/GLM/Doubao settings as OpenAI-compatible URLs.
    }

    private fun apiKey(provider: String, settings: JSONObject): String {
        val key = settings.optString("apiKey").trim()
        if (provider != PROVIDER_OLLAMA && key.isBlank()) throw IllegalArgumentException("API Key is empty.")
        return key
    }

    private fun modelOf(provider: String, settings: JSONObject): String = settings.optString("model").trim().ifBlank {
        when (provider) {
            PROVIDER_ANTHROPIC -> "claude-3-5-haiku-latest"
            PROVIDER_OLLAMA -> "qwen2.5:7b"
            else -> "gpt-4o-mini"
        }
    }

    private fun rootUrl(provider: String, settings: JSONObject): String {
        val configured = settings.optString("baseUrl").trim().trimEnd('/')
        return when {
            configured.isNotBlank() -> configured
            provider == PROVIDER_ANTHROPIC -> "https://api.anthropic.com/v1"
            provider == PROVIDER_OLLAMA -> "http://127.0.0.1:11434"
            else -> "https://api.openai.com/v1"
        }
    }

    private fun chatUrl(provider: String, settings: JSONObject): String {
        val root = rootUrl(provider, settings)
        return when (provider) {
            PROVIDER_ANTHROPIC -> if (root.endsWith("/messages")) root else "$root/messages"
            PROVIDER_OLLAMA -> if (root.endsWith("/api/chat")) root else "$root/api/chat"
            else -> if (root.endsWith("/chat/completions")) root else "$root/chat/completions"
        }
    }

    private fun modelsUrl(provider: String, settings: JSONObject): String {
        val root = rootUrl(provider, settings)
        return when (provider) {
            PROVIDER_ANTHROPIC -> if (root.endsWith("/models")) root else "$root/models"
            PROVIDER_OLLAMA -> if (root.endsWith("/api/tags")) root else "$root/api/tags"
            else -> "${root.removeSuffix("/chat/completions")}/models"
        }
    }

    private fun extractJsonObject(content: String): String {
        val noThink = content.replace(Regex("""<think>[\s\S]*?</think>"""), "").trim()
        val cleaned = if (noThink.contains("```")) {
            Regex("""```(?:json)?([\s\S]*?)```""").find(noThink)?.groupValues?.get(1)?.trim() ?: noThink
        } else noThink
        val start = cleaned.indexOf('{')
        if (start < 0) {
            val arrStart = cleaned.indexOf('[')
            val arrEnd = cleaned.lastIndexOf(']')
            if (arrStart >= 0 && arrEnd > arrStart) return cleaned.substring(arrStart, arrEnd + 1)
            throw IllegalStateException("AI response is not JSON: ${cleaned.take(500)}")
        }
        val end = cleaned.lastIndexOf('}')
        if (end > start) return cleaned.substring(start, end + 1)
        return cleaned.substring(start) + "\n}"
    }

    private fun parseTranslatedObject(jsonText: String): JSONObject {
        try {
            if (jsonText.startsWith("{")) return JSONObject(jsonText)
            if (jsonText.startsWith("[")) {
                val arr = org.json.JSONArray(jsonText)
                val obj = JSONObject()
                for (i in 0 until arr.length()) {
                    val item = arr.optJSONObject(i)
                    if (item != null) {
                        val k = item.optString("id").ifBlank { item.optString("entry_id").ifBlank { (i + 1).toString() } }
                        val v = item.optString("target").ifBlank { item.optString("translation") }
                        if (k.isNotBlank() && v.isNotBlank()) obj.put(k, v)
                    } else {
                        val str = arr.optString(i)
                        if (str.isNotBlank()) obj.put((i + 1).toString(), str)
                    }
                }
                return obj
            }
        } catch (_: Throwable) {}

        val recovered = JSONObject()
        val pairRegex = Regex(""""([^"\\]*(?:\\.[^"\\]*)*)"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"""")
        pairRegex.findAll(jsonText).forEach { match ->
            val key = match.groupValues[1]
            val value = match.groupValues[2]
                .replace("\\\"", "\"")
                .replace("\\\\", "\\")
                .replace("\\n", "\n")
                .replace("\\r", "\r")
                .replace("\\t", "\t")
            if (key.isNotBlank() && value.isNotBlank()) {
                recovered.put(key, value)
            }
        }
        if (recovered.length() > 0) return recovered
        throw IllegalStateException("AI returned unparseable JSON: ${jsonText.take(500)}")
    }
    private fun error(error: Throwable) = JSONObject().put("ok", false).put("error", error.message ?: error.javaClass.simpleName)

    companion object {
        private const val PROVIDER_OPENAI = "openai_compatible"
        private const val PROVIDER_ANTHROPIC = "anthropic_compatible"
        private const val PROVIDER_OLLAMA = "ollama"
        // Keep the mobile payload limit aligned with the desktop batch setting.
        private const val MAX_ENTRIES = 200
        private const val CONNECT_TIMEOUT_MS = 45_000
        private const val READ_TIMEOUT_MS = 120_000
    }
}

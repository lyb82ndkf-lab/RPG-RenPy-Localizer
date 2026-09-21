package com.rpgrtl.shell.rpgmaker

import android.content.Context
import android.webkit.JavascriptInterface
import com.rpgrtl.shell.ShellLog
import com.rpgrtl.shell.data.TranslationManager
import org.json.JSONObject
import java.io.File

/**
 * 暴露给 RPG Maker MV/MZ WebView 前端的 JavascriptInterface
 * 提供实时字典获取与热重载接口
 */
class TranslationHotReloadBridge(
    private val context: Context,
    private val gameDir: File
) {

    @JavascriptInterface
    fun getTranslationMap(): String {
        return runCatching {
            val transFile = TranslationManager.findTranslationFile(gameDir)
            if (transFile == null || !transFile.exists() || !transFile.isFile) {
                return "{}"
            }
            val text = transFile.readText(Charsets.UTF_8).trim()
            if (text.startsWith("{")) {
                val root = JSONObject(text)
                if (root.has("items")) {
                    val items = root.optJSONArray("items")
                    val map = JSONObject()
                    if (items != null) {
                        for (i in 0 until items.length()) {
                            val item = items.optJSONObject(i) ?: continue
                            val src = item.optString("src", "")
                            val dst = item.optString("dst", "")
                            if (src.isNotBlank() && dst.isNotBlank()) {
                                map.put(src, dst)
                            }
                        }
                    }
                    map.toString()
                } else {
                    text
                }
            } else {
                "{}"
            }
        }.getOrElse { error ->
            ShellLog.error(context, "TranslationHotReloadBridge getTranslationMap failed", error)
            "{}"
        }
    }
}

package com.rpgrtl.shell.rpgmaker

import android.content.Context
import android.webkit.JavascriptInterface
import com.rpgrtl.shell.ShellLog
import com.rpgrtl.shell.data.TranslationManager
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
            TranslationManager.getTranslationMapJson(gameDir)
        }.getOrElse { error ->
            ShellLog.error(context, "TranslationHotReloadBridge getTranslationMap failed", error)
            "{}"
        }
    }
}

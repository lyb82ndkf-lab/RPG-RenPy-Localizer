package com.rpgrtl.shell.rpgmaker

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.webkit.JavascriptInterface
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import com.rpgrtl.shell.ShellLog
import com.rpgrtl.shell.data.TranslationManager
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Native services exposed to the RPG Maker runtime and the full-screen dashboard. */
class RpgMakerNativeBridge(
    private val context: Context,
    private val gameDir: File,
    private val webRoot: File
) {
    private val translationBridge = TranslationHotReloadBridge(context, gameDir)
    private val saveDir: File by lazy { resolveSaveDirectory() }
    private val prefs by lazy { context.getSharedPreferences("rpgmaker_ingame_controls", Context.MODE_PRIVATE) }

    @JavascriptInterface fun getTranslationMap(): String = translationBridge.getTranslationMap()
    @JavascriptInterface fun getSaveDirectory(): String = saveDir.absolutePath
    @JavascriptInterface fun saveFileExists(fileName: String): Boolean = safeSaveFile(fileName)?.isFile == true

    @JavascriptInterface
    fun loadSaveData(fileName: String): String {
        val file = safeSaveFile(fileName) ?: return ""
        if (!file.isFile) return ""
        return runCatching { file.readText(Charsets.UTF_8) }
            .onFailure { ShellLog.error(context, "RPG Maker save read failed: ${file.absolutePath}", it) }
            .getOrDefault("")
    }

    @JavascriptInterface
    fun saveSaveData(fileName: String, data: String): Boolean {
        val file = safeSaveFile(fileName) ?: return false
        return runCatching {
            if (!saveDir.exists() && !saveDir.mkdirs()) error("Unable to create save directory: ${saveDir.absolutePath}")
            val temp = File(saveDir, ".${file.name}.rpgrtl.tmp")
            temp.writeText(data, Charsets.UTF_8)
            if (file.exists() && !file.delete()) {
                temp.delete()
                error("Unable to replace save file: ${file.absolutePath}")
            }
            if (!temp.renameTo(file)) {
                temp.copyTo(file, overwrite = true)
                temp.delete()
            }
            true
        }.onFailure { ShellLog.error(context, "RPG Maker save write failed: ${file.absolutePath}", it) }
            .getOrDefault(false)
    }

    @JavascriptInterface
    fun removeSaveFile(fileName: String): Boolean {
        val file = safeSaveFile(fileName) ?: return false
        if (!file.exists()) return true
        return runCatching { file.delete() }
            .onFailure { ShellLog.error(context, "RPG Maker save delete failed: ${file.absolutePath}", it) }
            .getOrDefault(false)
    }

    @JavascriptInterface
    fun createSaveBackup(): String = runCatching {
        if (!saveDir.isDirectory) return JSONObject().put("ok", false).put("error", "尚无存档目录").toString()
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val target = File(saveDir, ".rpgrtl_backup/$stamp").apply { mkdirs() }
        val files = saveDir.listFiles()?.filter {
            it.isFile && (it.name.endsWith(".rpgsave", true) || it.name.endsWith(".rmmzsave", true))
        }.orEmpty()
        files.forEach { it.copyTo(File(target, it.name), overwrite = true) }
        JSONObject().put("ok", true).put("name", stamp).put("files", files.size).put("path", target.absolutePath).toString()
    }.getOrElse { JSONObject().put("ok", false).put("error", it.message.orEmpty()).toString() }

    @JavascriptInterface
    fun listSaveBackups(): String {
        val root = File(saveDir, ".rpgrtl_backup")
        val result = JSONArray()
        root.listFiles()?.filter { it.isDirectory }?.sortedByDescending { it.name }?.take(50)?.forEach { dir ->
            result.put(JSONObject().put("name", dir.name).put("time", dir.name.replace('_', ' '))
                .put("files", dir.listFiles()?.count { it.isFile } ?: 0).put("path", dir.absolutePath))
        }
        return result.toString()
    }

    @JavascriptInterface
    fun getTranslationInfo(): String = runCatching {
        val file = TranslationManager.findTranslationFile(gameDir)
        val map = JSONObject(getTranslationMap())
        JSONObject()
            .put("exists", file?.isFile == true)
            .put("fileName", file?.name ?: "翻译文件.json")
            .put("entryCount", map.length())
            .put("sizeBytes", file?.length() ?: 0L)
            .put("sizeLabel", formatBytes(file?.length() ?: 0L))
            .toString()
    }.getOrElse { JSONObject().put("exists", false).put("entryCount", 0).put("sizeLabel", "0 B").toString() }

    @JavascriptInterface
    fun translationAction(mode: String): String {
        LocalBroadcastManager.getInstance(context).sendBroadcast(
            Intent("com.rpgrtl.TRANSLATION_ACTION").putExtra("mode", mode).putExtra("game_dir", gameDir.absolutePath)
        )
        return when (mode) {
            "load" -> "已请求加载翻译文件"
            "restore" -> "已请求还原原文"
            "export" -> "已请求导出外部翻译文本"
            "rescan" -> "已请求重新获取文本"
            "terms" -> "已打开名词修正流程"
            "start" -> "已发送到主界面翻译任务"
            else -> "翻译操作已发送"
        }
    }

    @JavascriptInterface
    fun getGamepadProfile(): String = prefs.getString("gamepad_profile_json", "").orEmpty()

    @JavascriptInterface
    fun saveGamepadProfile(json: String): Boolean = runCatching {
        JSONObject(json) // validate before persisting
        check(prefs.edit().putString("gamepad_profile_json", json).commit()) { "Unable to persist gamepad profile" }
        Handler(Looper.getMainLooper()).post {
            (context as? RpgMakerWebViewActivity)?.applyGamepadProfile(json)
        }
        true
    }.getOrDefault(false)

    @JavascriptInterface
    fun setDashboardVisible(visible: Boolean) {
        Handler(Looper.getMainLooper()).post {
            (context as? RpgMakerWebViewActivity)?.onDashboardVisibilityChanged(visible)
        }
    }

    @JavascriptInterface
    fun setSilentKeepAlive(enabled: Boolean): Boolean {
        prefs.edit().putBoolean("silent_keepalive", enabled).apply()
        return true
    }

    @JavascriptInterface
    fun vibrate(durationMs: Int, strength: Int) {
        Handler(Looper.getMainLooper()).post {
            (context as? RpgMakerWebViewActivity)?.vibrateFromDashboard(durationMs, strength)
        }
    }

    @JavascriptInterface
    fun requestExit() {
        Handler(Looper.getMainLooper()).post { (context as? Activity)?.finish() }
    }

    private fun resolveSaveDirectory(): File {
        val rootSave = File(gameDir, "save")
        val webSave = File(webRoot, "save")
        val existingWithSaves = listOf(rootSave, webSave).distinctBy { it.absolutePath }.firstOrNull { dir ->
            dir.isDirectory && dir.listFiles()?.any { file ->
                file.isFile && (file.name.endsWith(".rpgsave", true) || file.name.endsWith(".rmmzsave", true))
            } == true
        }
        val chosen = existingWithSaves ?: rootSave
        if (!chosen.exists()) chosen.mkdirs()
        ShellLog.info(context, "RPG Maker physical save directory: ${chosen.absolutePath}")
        return chosen
    }

    private fun safeSaveFile(fileName: String): File? {
        val name = fileName.trim()
        if (name.isBlank() || name.indexOf('\u0000') >= 0) return null
        return runCatching {
            val canonicalDir = saveDir.canonicalFile
            val candidate = File(canonicalDir, name).canonicalFile
            if (candidate.parentFile != canonicalDir) {
                ShellLog.info(context, "Rejected unsafe RPG Maker save path: $fileName")
                null
            } else candidate
        }.getOrNull()
    }

    private fun formatBytes(bytes: Long): String = when {
        bytes >= 1024 * 1024 -> String.format(Locale.US, "%.1f MB", bytes / 1048576.0)
        bytes >= 1024 -> String.format(Locale.US, "%.1f KB", bytes / 1024.0)
        else -> "$bytes B"
    }
}

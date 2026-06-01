package com.rpgrtl.shell.wine

import android.content.Context
import com.rpgrtl.engine.container.Container
import com.rpgrtl.engine.container.ContainerManager
import com.rpgrtl.engine.xenvironment.RootFS
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class WineSaveService(private val context: Context) {
    fun saveSlots(containerId: Int, gamePath: String): JSONObject {
        val container = findContainer(containerId) ?: return error("Wine container not found.")
        val saveDir = detectSaveDir(container, gamePath)
        val slots = JSONArray()
        if (saveDir != null) {
            saveDir.listFiles()
                ?.filter { it.isFile && SAVE_FILE_REGEX.matches(it.name) }
                ?.sortedBy { it.name.lowercase(Locale.ENGLISH) }
                ?.forEach { file ->
                    val match = SAVE_FILE_REGEX.matchEntire(file.name)
                    slots.put(
                        JSONObject()
                            .put("slot_id", match?.groupValues?.getOrNull(1)?.toIntOrNull() ?: extractSlot(file.name))
                            .put("label", "Save ${extractSlot(file.name).takeIf { it >= 0 } ?: ""}".trim())
                            .put("name", file.name)
                            .put("path", file.absolutePath)
                            .put("save_root", saveDir.absolutePath)
                            .put("source", "wine")
                            .put("size", file.length())
                            .put("modified_at", formatTime(file.lastModified()))
                    )
                }
        }
        return JSONObject()
            .put("ok", true)
            .put("wine", true)
            .put("container_id", container.id)
            .put("save_path", saveDir?.absolutePath ?: "")
            .put("count", slots.length())
            .put("slots", slots)
    }

    fun createBackup(containerId: Int, gamePath: String): JSONObject {
        val container = findContainer(containerId) ?: return error("Wine container not found.")
        val saveDir = detectSaveDir(container, gamePath) ?: return error("Wine save directory not found.")
        val backupDir = File(saveDir, "mtool/backup/save").apply { mkdirs() }
        var copied = 0
        saveDir.listFiles()
            ?.filter { it.isFile && SAVE_FILE_REGEX.matches(it.name) }
            ?.forEach { file ->
                file.copyTo(File(backupDir, "${file.name}.${stamp()}.bak"), overwrite = true)
                copied += 1
            }
        return JSONObject()
            .put("ok", true)
            .put("message", "Backed up $copied Wine save files.")
            .put("count", copied)
            .put("backup_path", backupDir.absolutePath)
    }

    fun backups(containerId: Int, gamePath: String): JSONObject {
        val container = findContainer(containerId) ?: return error("Wine container not found.")
        val saveDir = detectSaveDir(container, gamePath)
        val backupDirs = listOfNotNull(
            saveDir?.let { File(it, "mtool/backup/save") },
            saveDir?.let { File(it, ".rpgrtl_backup") }
        )
        val backups = JSONArray()
        backupDirs.forEach { backupDir ->
            backupDir.listFiles()
                ?.filter { it.isFile }
                ?.sortedByDescending { it.lastModified() }
                ?.forEach { file ->
                    backups.put(
                        JSONObject()
                            .put("name", file.name)
                            .put("path", file.absolutePath)
                            .put("size", file.length())
                            .put("modified_at", formatTime(file.lastModified()))
                    )
                }
            }
        return JSONObject()
            .put("ok", true)
            .put("wine", true)
            .put("count", backups.length())
            .put("backups", backups)
    }

    fun savePath(containerId: Int, gamePath: String): JSONObject {
        val container = findContainer(containerId) ?: return error("Wine container not found.")
        val saveDir = detectSaveDir(container, gamePath)
        return JSONObject()
            .put("ok", true)
            .put("wine", true)
            .put("exists", saveDir != null)
            .put("savePath", saveDir?.absolutePath ?: "")
            .put("container_id", container.id)
    }

    private fun findContainer(containerId: Int): Container? {
        val manager = ContainerManager(context)
        return if (containerId > 0) {
            manager.getContainerById(containerId)
        } else {
            manager.containers.firstOrNull()
        }
    }

    private fun detectSaveDir(container: Container, gamePath: String): File? {
        val gameDir = File(gamePath.removePrefix("file://")).parentFile
        val driveC = File(container.rootDir, ".wine/drive_c")
        val userDir = File(driveC, "users/${RootFS.USER}")
        val candidates = listOfNotNull(
            gameDir?.resolve("www/save"),
            gameDir?.resolve("save"),
            gameDir?.resolve("Save"),
            gameDir?.resolve("game/saves"),
            gameDir?.resolve("saves"),
            gameDir?.resolve("Saves"),
            gameDir?.resolve("Saved"),
            gameDir?.resolve("Saved/SaveGames"),
            driveC.resolve("www/save"),
            driveC.resolve("save"),
            driveC.resolve("Save"),
            driveC.resolve("saves"),
            userDir.resolve("AppData/Roaming"),
            userDir.resolve("AppData/Local")
        )
        candidates.firstOrNull { it.isDirectory && hasSaveFiles(it, deep = false) }?.let { return it }
        return candidates
            .filter { it.isDirectory }
            .firstOrNull { hasSaveFiles(it, deep = true) }
            ?.let { dir ->
                dir.walkTopDown()
                    .filter { it.isDirectory && hasSaveFiles(it, deep = false) }
                    .maxByOrNull { it.listFiles()?.count { file -> file.isFile && SAVE_FILE_REGEX.matches(file.name) } ?: 0 }
            }
    }

    private fun hasSaveFiles(dir: File, deep: Boolean): Boolean {
        val files = if (deep) dir.walkTopDown().take(3000) else dir.listFiles()?.asSequence() ?: emptySequence()
        return files.any { it.isFile && SAVE_FILE_REGEX.matches(it.name) }
    }

    private fun formatTime(ms: Long): String {
        return SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date(ms))
    }

    private fun stamp(): String {
        return SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
    }

    private fun extractSlot(name: String): Int {
        return Regex("""\d+""").find(name)?.value?.toIntOrNull() ?: -1
    }

    private fun error(message: String): JSONObject {
        return JSONObject().put("ok", false).put("error", message)
    }

    companion object {
        private val SAVE_FILE_REGEX = Regex("""(?:file|save|slot|autosave|auto|quick)?(\d*)[^/\\]*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|sav|lsd|dat|bin|json|ini|profile|slot)""", RegexOption.IGNORE_CASE)
    }
}

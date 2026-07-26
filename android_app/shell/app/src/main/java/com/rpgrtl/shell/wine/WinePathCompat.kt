package com.rpgrtl.shell.wine

import android.content.Context
import com.rpgrtl.engine.core.FileUtils
import com.rpgrtl.engine.xenvironment.RootFS
import com.rpgrtl.shell.ShellLog
import java.io.File
import java.io.RandomAccessFile

/**
 * Winlator rootfs hardcodes `/data/data/com.winlator/files/rootfs` in nearly every .so
 * (ntdll wineserver sockets, ld-linux, libX11, gladio, …).
 *
 * Our package is longer (`com.rpgrtl.shell`), so we:
 *  1) create short bridge `files/w` -> real rootfs
 *  2) binary-patch every C string that starts with the old prefix, rewriting the full
 *     null-terminated string so suffixes like `/tmp/.wine-%u/...` stay intact.
 */
object WinePathCompat {
    const val SHORT_ROOTFS_NAME = "w"
    const val SHORT_CACHE_NAME = "c"
    const val OLD_ROOTFS_PREFIX = "/data/data/com.winlator/files/rootfs"

    fun shortRootfsLink(context: Context): File = File(context.filesDir, SHORT_ROOTFS_NAME)

    fun newRootfsPrefix(context: Context): String =
        "/data/data/${context.packageName}/files/$SHORT_ROOTFS_NAME"

    fun newLibPath(context: Context): String = newRootfsPrefix(context) + "/lib"

    fun newX11Path(context: Context): String =
        newRootfsPrefix(context) + "/tmp/.X11-unix/X0"

    fun ensureBridge(context: Context): Boolean {
        val rootfs = RootFS.find(context).rootDir
        if (!rootfs.isDirectory) return false
        val link = shortRootfsLink(context)
        return try {
            val target = rootfs.absolutePath
            if (link.exists() || FileUtils.isSymlink(link)) {
                val ok = try {
                    link.canonicalPath == rootfs.canonicalPath
                } catch (_: Throwable) {
                    false
                }
                if (!ok) {
                    FileUtils.delete(link)
                    FileUtils.symlink(target, link.absolutePath)
                }
            } else {
                FileUtils.symlink(target, link.absolutePath)
            }
            File(context.filesDir, SHORT_CACHE_NAME).mkdirs()
            File(rootfs, "tmp/.X11-unix").mkdirs()
            File(rootfs, "tmp/.sound").mkdirs()
            File(rootfs, "tmp/.sysvshm").mkdirs()
            File(rootfs, "tmp/shm").mkdirs()
            val libDir = File(rootfs, "lib")
            val usrLib = File(rootfs, "usr/lib")
            if (usrLib.isDirectory && !libDir.exists()) {
                FileUtils.symlink(usrLib.absolutePath, libDir.absolutePath)
            }
            ShellLog.info(
                context,
                "Wine path bridge ${link.absolutePath} -> $target " +
                    "newPrefix=${newRootfsPrefix(context)} exists=${link.exists()}"
            )
            link.exists()
        } catch (error: Throwable) {
            ShellLog.error(context, "Wine path bridge failed", error)
            false
        }
    }

    fun patchGuestGladio(context: Context): Boolean {
        ensureBridge(context)
        val rootfs = RootFS.find(context).rootDir
        val lib = listOf(
            File(rootfs, "usr/lib/libGL.so.1.7.0"),
            File(rootfs, "usr/lib/libGL.so.1"),
            File(rootfs, "usr/lib/libGL.so")
        ).firstOrNull { it.isFile }
        if (lib == null) {
            ShellLog.info(context, "patchGuestGladio: libGL not found")
            return false
        }
        val n = patchFileInPlace(lib, OLD_ROOTFS_PREFIX, newRootfsPrefix(context))
        ShellLog.info(context, "patchGuestGladio ${lib.name} replacements=$n")
        return n > 0 || lib.isFile
    }

    fun patchCoreRuntimePaths(context: Context): Int {
        ensureBridge(context)
        val rootfs = RootFS.find(context).rootDir
        if (!rootfs.isDirectory) return 0
        val oldP = OLD_ROOTFS_PREFIX
        val newP = newRootfsPrefix(context)
        if (newP.length > oldP.length) {
            ShellLog.error(context, "Cannot patch core paths: new prefix longer ($newP)")
            return 0
        }

        val marker = File(rootfs, ".winlator/rpgtl_core_path_patched_v1")
        val expected = "$oldP=>$newP"
        val targets = buildCorePatchTargets(rootfs)
        if (marker.isFile && runCatching { marker.readText() }.getOrDefault("") == expected) {
            ShellLog.info(context, "Core path patch already applied targets=${targets.size}")
            return 0
        }

        var filesTouched = 0
        var replacements = 0
        targets.forEachIndexed { index, file ->
            if (!file.isFile || file.length() <= 0L) return@forEachIndexed
            if (file.length() > 96L * 1024L * 1024L) {
                ShellLog.info(context, "Core path patch skip large ${file.name} size=${file.length()}")
                return@forEachIndexed
            }
            val count = try {
                patchFileInPlace(file, oldP, newP)
            } catch (error: Throwable) {
                ShellLog.error(context, "Core path patch failed for ${file.absolutePath}", error)
                0
            }
            if (count > 0) {
                filesTouched++
                replacements += count
            }
        }

        marker.parentFile?.mkdirs()
        FileUtils.writeString(marker, expected)
        ShellLog.info(
            context,
            "Core path patch done files=$filesTouched replacements=$replacements old=$oldP new=$newP"
        )
        return replacements
    }

    private fun buildCorePatchTargets(rootfs: File): List<File> {
        val direct = mutableListOf(
            File(rootfs, "usr/local/bin/box64"),
            File(rootfs, "opt/wine/bin/wine"),
            File(rootfs, "opt/wine/bin/wine64"),
            File(rootfs, "opt/wine/bin/wineserver"),
            File(rootfs, "opt/wine/bin/wineboot"),
            File(rootfs, "opt/wine/lib/wine/x86_64-unix/ntdll.so"),
            File(rootfs, "opt/wine/lib/wine/x86_64-unix/kernel32.so"),
            File(rootfs, "opt/wine/lib/wine/x86_64-unix/kernelbase.so"),
            File(rootfs, "usr/lib/libGL.so"),
            File(rootfs, "usr/lib/libGL.so.1"),
            File(rootfs, "usr/lib/libGL.so.1.7.0"),
            File(rootfs, "usr/lib/libX11.so"),
            File(rootfs, "usr/lib/libX11.so.6"),
            File(rootfs, "usr/lib/libxcb.so"),
            File(rootfs, "usr/lib/libxcb.so.1"),
            File(rootfs, "usr/lib/libvulkan.so"),
            File(rootfs, "usr/lib/libvulkan.so.1")
        )
        listOf(
            File(rootfs, "usr/lib"),
            File(rootfs, "usr/local/lib"),
            File(rootfs, "opt/wine/lib")
        ).forEach { dir ->
            dir.listFiles()?.forEach { file ->
                val name = file.name
                if (file.isFile && (name.endsWith(".so") || name.contains(".so."))) {
                    direct += file
                }
            }
        }
        return direct.distinctBy { it.absolutePath }
    }

    /**
     * box64 is a glibc aarch64 ELF whose PT_INTERP is hardcoded to
     * /data/data/com.winlator/files/rootfs/lib/ld-linux-aarch64.so.1
     * If not patched, Android execve fails instantly → no WINE logs, pure black screen.
     */
    fun patchBox64Interpreter(context: Context): Boolean {
        ensureBridge(context)
        val rootfs = RootFS.find(context).rootDir
        val box64 = File(rootfs, "usr/local/bin/box64")
        if (!box64.isFile) {
            ShellLog.info(context, "patchBox64: missing ${box64.absolutePath}")
            return false
        }
        val n = patchFileInPlace(box64, OLD_ROOTFS_PREFIX, newRootfsPrefix(context))
        FileUtils.chmod(box64, 0b111_101_101) // 0755
        // Ensure interpreter target exists via lib -> usr/lib bridge
        val ld = File(rootfs, "lib/ld-linux-aarch64.so.1")
        val ldUsr = File(rootfs, "usr/lib/ld-linux-aarch64.so.1")
        if (!ld.exists() && ldUsr.isFile) {
            try {
                FileUtils.symlink(ldUsr.absolutePath, ld.absolutePath)
            } catch (_: Throwable) {
            }
        }
        val expectedInterp = newRootfsPrefix(context) + "/lib/ld-linux-aarch64.so.1"
        val hasOld = containsAscii(box64, OLD_ROOTFS_PREFIX)
        val hasNew = containsAscii(box64, newRootfsPrefix(context))
        ShellLog.info(
            context,
            "patchBox64 replacements=$n size=${box64.length()} " +
                "hasOldPrefix=$hasOld hasNewPrefix=$hasNew " +
                "expectedInterp=$expectedInterp ldExists=${ld.exists() || ldUsr.isFile}"
        )
        return !hasOld && hasNew
    }

    fun containsAscii(file: File, needle: String): Boolean {
        return try {
            val data = file.readBytes()
            indexOf(data, needle.toByteArray(Charsets.US_ASCII), 0) >= 0
        } catch (_: Throwable) {
            false
        }
    }

    fun patchEntireRootfs(context: Context): Int {
        ensureBridge(context)
        val rootfs = RootFS.find(context).rootDir
        if (!rootfs.isDirectory) return 0
        val oldP = OLD_ROOTFS_PREFIX
        val newP = newRootfsPrefix(context)
        if (newP.length > oldP.length) {
            ShellLog.error(context, "Cannot patch: new prefix longer ($newP)")
            return 0
        }
        val marker = File(rootfs, ".winlator/rpgtl_path_patched_v4")
        val expected = "$oldP=>$newP"
        if (marker.isFile && runCatching { marker.readText() }.getOrDefault("") == expected) {
            ShellLog.info(context, "Rootfs path patch already applied ($expected)")
            return 0
        }

        var filesTouched = 0
        var total = 0
        rootfs.walkTopDown().forEach { file ->
            if (!file.isFile || file.length() == 0L) return@forEach
            if (file.name.startsWith("rpgtl_path_patched")) return@forEach
            val name = file.name.lowercase()
            if (name.endsWith(".png") || name.endsWith(".jpg") || name.endsWith(".ttf") ||
                name.endsWith(".ogg") || name.endsWith(".wav") || name.endsWith(".mp3") ||
                name.endsWith(".rpa") || name.endsWith(".rpyc")
            ) {
                return@forEach
            }
            try {
                val n = patchFileInPlace(file, oldP, newP)
                if (n > 0) {
                    filesTouched++
                    total += n
                }
            } catch (_: Throwable) {
            }
        }
        marker.parentFile?.mkdirs()
        FileUtils.writeString(marker, expected)
        ShellLog.info(
            context,
            "Rootfs path patch done files=$filesTouched replacements=$total old=$oldP new=$newP"
        )
        return total
    }

    /**
     * For every occurrence of [oldPrefix] as the start of a C string (or embedded path),
     * rewrite the full null-terminated string: replace prefix, keep suffix, zero-fill the
     * leftover tail of the original string slot.
     */
    fun patchFileInPlace(file: File, oldPrefix: String, newPrefix: String): Int {
        if (!file.isFile || newPrefix.length > oldPrefix.length) return 0
        val original = try {
            file.readBytes()
        } catch (_: Throwable) {
            return 0
        }
        val data = original.copyOf()
        val oldB = oldPrefix.toByteArray(Charsets.US_ASCII)
        val newB = newPrefix.toByteArray(Charsets.US_ASCII)
        var count = 0
        var idx = 0
        while (true) {
            val found = indexOf(data, oldB, idx)
            if (found < 0) break
            // Find end of C string (null terminator), cap scan to avoid huge runs.
            var end = found
            val maxEnd = minOf(data.size, found + 512)
            while (end < maxEnd && data[end] != 0.toByte()) end++
            if (end >= maxEnd) {
                // No null within window — treat as fixed-length field of oldPrefix only.
                end = found + oldB.size
            }
            val oldFullLen = end - found // without null
            val hasNull = end < data.size && data[end] == 0.toByte()
            val suffixStart = found + oldB.size
            val suffixLen = (oldFullLen - oldB.size).coerceAtLeast(0)
            val newFullLen = newB.size + suffixLen
            if (newFullLen > oldFullLen) {
                // Would need more room than original string slot — skip.
                idx = found + oldB.size
                continue
            }
            // Write new prefix
            for (i in newB.indices) data[found + i] = newB[i]
            // Copy suffix immediately after new prefix
            if (suffixLen > 0) {
                System.arraycopy(data, suffixStart, data, found + newB.size, suffixLen)
            }
            // Zero-fill remainder of original slot (including old null position area)
            val fillFrom = found + newFullLen
            val fillTo = if (hasNull) end + 1 else end
            for (i in fillFrom until fillTo) data[i] = 0
            count++
            idx = found + oldB.size
        }
        if (count > 0) {
            try {
                RandomAccessFile(file, "rw").use { raf ->
                    raf.setLength(data.size.toLong())
                    raf.seek(0)
                    raf.write(data)
                }
                file.setReadable(true, false)
                try {
                    file.setExecutable(true, false)
                } catch (_: Throwable) {
                }
            } catch (_: Throwable) {
                return 0
            }
        }
        return count
    }

    private fun indexOf(data: ByteArray, pattern: ByteArray, from: Int): Int {
        outer@ for (i in from..(data.size - pattern.size)) {
            for (j in pattern.indices) {
                if (data[i + j] != pattern[j]) continue@outer
            }
            return i
        }
        return -1
    }
}

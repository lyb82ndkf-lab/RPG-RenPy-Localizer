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

    fun patchVulkanIcds(context: Context): Int {
        ensureBridge(context)
        val rootfs = RootFS.find(context).rootDir
        if (!rootfs.isDirectory) return 0
        val icdDir = File(rootfs, "usr/share/vulkan/icd.d")
        val oldP = OLD_ROOTFS_PREFIX
        val newP = newRootfsPrefix(context)
        var count = 0

        // Ensure libvulkan_freedreno.so is visible in rootfs/lib as well as rootfs/usr/lib
        val turnipUsr = File(rootfs, "usr/lib/libvulkan_freedreno.so")
        val turnipLib = File(rootfs, "lib/libvulkan_freedreno.so")
        if (turnipUsr.isFile && !turnipLib.exists()) {
            try {
                FileUtils.symlink(turnipUsr.absolutePath, turnipLib.absolutePath)
            } catch (_: Throwable) {
            }
        }

        if (icdDir.isDirectory) {
            icdDir.listFiles()?.filter { it.isFile && it.name.endsWith(".json") }?.forEach { file ->
                try {
                    var text = file.readText()
                    var modified = false
                    if (text.contains(oldP)) {
                        text = text.replace(oldP, newP)
                        modified = true
                    }
                    if (file.name.contains("freedreno")) {
                        val expectedPath = "$newP/usr/lib/libvulkan_freedreno.so"
                        if (!text.contains(expectedPath) && !text.contains("$newP/lib/libvulkan_freedreno.so")) {
                            text = "{\n    \"ICD\": {\n        \"api_version\": \"1.4.318\",\n        \"library_arch\": \"64\",\n        \"library_path\": \"$expectedPath\"\n    },\n    \"file_format_version\": \"1.0.1\"\n}\n"
                            modified = true
                        }
                    } else if (file.name.contains("vortek")) {
                        val expectedPath = "$newP/usr/lib/libvulkan_vortek.so"
                        if (!text.contains(expectedPath) && !text.contains("$newP/lib/libvulkan_vortek.so")) {
                            text = "{\n    \"ICD\": {\n        \"api_version\": \"1.1.128\",\n        \"library_path\": \"$expectedPath\"\n    },\n    \"file_format_version\": \"1.0.0\"\n}\n"
                            modified = true
                        }
                    }
                    if (modified) {
                        file.writeText(text)
                        count++
                        ShellLog.info(context, "Patched Vulkan ICD ${file.name} to $newP")
                    }
                } catch (t: Throwable) {
                    ShellLog.error(context, "Failed to patch Vulkan ICD ${file.name}", t)
                }
            }
        }
        return count
    }

    fun patchCoreRuntimePaths(context: Context): Int {
        ensureBridge(context)
        patchVulkanIcds(context)
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
            File(rootfs, "usr/lib/libvulkan.so.1"),
            File(rootfs, "usr/lib/libvulkan.so.1.3.301")
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

    fun findHostCjkFont(): File? {
        val searchDirs = listOf(
            File("/system/fonts"),
            File("/product/fonts"),
            File("/system_ext/fonts")
        )
        val preferredNames = listOf(
            "NotoSansCJK-Regular.ttc",
            "NotoSansSC-Regular.otf",
            "NotoSansSC-Regular.ttf",
            "NotoSansHans-Regular.otf",
            "NotoSansHans-Regular.ttf",
            "DroidSansFallback.ttf",
            "MiSans-Regular.ttf",
            "HarmonyOS_Sans_SC.ttf",
            "OPPOSans-Regular.ttf",
            "HONOR_Sans_Chinese-Regular.ttf",
            "SourceHanSansCN-Regular.otf",
            "SourceHanSans-Regular.ttc",
            "FZLanTingHei-R-GBK.ttf"
        )

        for (dir in searchDirs) {
            if (!dir.isDirectory) continue
            for (name in preferredNames) {
                val f = File(dir, name)
                if (f.isFile && f.length() > 100_000) return f
            }
        }

        for (dir in searchDirs) {
            if (!dir.isDirectory) continue
            val match = dir.listFiles()?.firstOrNull { file ->
                if (!file.isFile || file.length() < 500_000) return@firstOrNull false
                val lower = file.name.lowercase(java.util.Locale.ROOT)
                (lower.contains("cjk") || lower.contains("sc-") || lower.contains("hans") ||
                    lower.contains("fallback") || lower.contains("chinese") || lower.contains("misans") ||
                    lower.contains("harmonyos")) && (lower.endsWith(".ttf") || lower.endsWith(".otf") || lower.endsWith(".ttc"))
            }
            if (match != null) return match
        }

        for (dir in searchDirs) {
            if (!dir.isDirectory) continue
            val largeFont = dir.listFiles()?.firstOrNull { file ->
                file.isFile && file.length() > 4_000_000 &&
                    (file.name.endsWith(".ttf") || file.name.endsWith(".otf") || file.name.endsWith(".ttc"))
            }
            if (largeFont != null) return largeFont
        }

        return null
    }

    private fun linkOrCopyFont(source: File, target: File): Boolean {
        if (target.exists() || FileUtils.isSymlink(target)) {
            if (target.length() > 0) return true
            FileUtils.delete(target)
        }
        target.parentFile?.mkdirs()
        val linked = runCatching {
            FileUtils.symlink(source.absolutePath, target.absolutePath)
            target.exists() && target.length() > 0
        }.getOrDefault(false)
        if (linked) return true

        return runCatching {
            FileUtils.copy(source, target)
            target.isFile && target.length() > 0
        }.getOrDefault(false)
    }

    fun setupCjkFonts(context: Context, containerDir: File): Boolean {
        val rootfs = RootFS.find(context).rootDir
        val hostCjkFont = findHostCjkFont()
        if (hostCjkFont == null) {
            ShellLog.error(context, "No CJK font found in /system/fonts or /product/fonts", null)
            return false
        }
        ShellLog.info(context, "Using host CJK font: ${hostCjkFont.absolutePath} (size=${hostCjkFont.length()} bytes)")

        val winFontsDir = File(containerDir, ".wine/drive_c/windows/Fonts")
        val wineShareFontsDir = File(rootfs, "opt/wine/share/wine/fonts")
        val linuxCjkFontsDir = File(rootfs, "usr/share/fonts/truetype/cjk")

        listOf(winFontsDir, wineShareFontsDir, linuxCjkFontsDir).forEach { it.mkdirs() }

        val standardFontAliases = listOf(
            "simsun.ttc",
            "simsun.ttf",
            "msyh.ttc",
            "msyh.ttf",
            "simhei.ttf",
            "simkai.ttf",
            "simfang.ttf",
            "msgothic.ttc"
        )

        for (alias in standardFontAliases) {
            linkOrCopyFont(hostCjkFont, File(winFontsDir, alias))
            linkOrCopyFont(hostCjkFont, File(wineShareFontsDir, alias))
        }
        linkOrCopyFont(hostCjkFont, File(linuxCjkFontsDir, "cjk_font.ttf"))

        patchFontconfigConf(context, rootfs)
        configureFontRegistry(context, containerDir)
        return true
    }

    private fun patchFontconfigConf(context: Context, rootfs: File) {
        val fontsConf = File(rootfs, "etc/fonts/fonts.conf")
        val cacheDir = File(rootfs, "var/cache/fontconfig")
        cacheDir.mkdirs()

        if (fontsConf.isFile) {
            runCatching {
                var content = fontsConf.readText()
                val oldP = OLD_ROOTFS_PREFIX
                val newP = newRootfsPrefix(context)
                if (content.contains(oldP)) {
                    content = content.replace(oldP, newP)
                    fontsConf.writeText(content)
                    ShellLog.info(context, "Patched fontconfig fonts.conf with $newP")
                }
            }.onFailure { error ->
                ShellLog.error(context, "Failed to patch fonts.conf", error)
            }
        }
    }

    private fun configureFontRegistry(context: Context, containerDir: File) {
        val regFiles = listOf(
            File(containerDir, ".wine/system.reg"),
            File(containerDir, ".wine/user.reg")
        )

        val fontLinks = listOf(
            "Tahoma",
            "Arial",
            "Segoe UI",
            "Microsoft Sans Serif",
            "MS Sans Serif",
            "Lucida Sans Unicode",
            "System",
            "Times New Roman",
            "Courier New"
        )
        val linkTargets = arrayOf("simsun.ttc,SimSun", "msyh.ttc,Microsoft YaHei")

        val fontSubstitutes = listOf(
            "SimSun" to "SimSun",
            "宋体" to "SimSun",
            "NSimSun" to "SimSun",
            "新宋体" to "SimSun",
            "SimHei" to "SimHei",
            "黑体" to "SimHei",
            "Microsoft YaHei" to "Microsoft YaHei",
            "微软雅黑" to "Microsoft YaHei",
            "KaiTi" to "KaiTi",
            "楷体" to "KaiTi",
            "FangSong" to "FangSong",
            "仿宋" to "FangSong",
            "MS Gothic" to "SimSun",
            "MS PGothic" to "SimSun",
            "MS UI Gothic" to "SimSun",
            "MingLiU" to "SimSun",
            "PMingLiU" to "SimSun"
        )

        val fontList = listOf(
            "SimSun & NSimSun (TrueType)" to "simsun.ttc",
            "Microsoft YaHei & Microsoft YaHei UI (TrueType)" to "msyh.ttc",
            "SimHei (TrueType)" to "simhei.ttf",
            "KaiTi (TrueType)" to "simkai.ttf",
            "FangSong (TrueType)" to "simfang.ttf"
        )

        for (regFile in regFiles) {
            if (!regFile.isFile) continue
            runCatching {
                com.rpgrtl.engine.core.WineRegistryEditor(regFile).use { reg ->
                    val fontKey = "Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts"
                    for ((k, v) in fontList) {
                        reg.setStringValue(fontKey, k, v)
                    }

                    val subKey = "Software\\Microsoft\\Windows NT\\CurrentVersion\\FontSubstitutes"
                    for ((k, v) in fontSubstitutes) {
                        reg.setStringValue(subKey, k, v)
                    }

                    val linkKey = "Software\\Microsoft\\Windows NT\\CurrentVersion\\FontLink\\SystemLink"
                    for (face in fontLinks) {
                        reg.setMultiStringValue(linkKey, face, linkTargets)
                    }
                }
                ShellLog.info(context, "Configured CJK fonts & FontLink in ${regFile.name}")
            }.onFailure { error ->
                ShellLog.error(context, "Failed to write font registry to ${regFile.name}", error)
            }
        }
    }

    fun setupDxvkConfig(context: Context, rootDir: File): File {
        val etcDir = File(rootDir, "etc")
        etcDir.mkdirs()
        val confFile = File(etcDir, "dxvk.conf")
        val content = """
            # RPGRenPyLocalizer optimized DXVK configuration
            # Enforce VSync, tearFree, and strict frame presentation pacing to eliminate screen flickering
            dxgi.syncInterval = 1
            d3d11.syncInterval = 1
            d3d9.presentInterval = 1
            dxgi.tearFree = True
            d3d9.tearFree = True
            dxgi.maxFrameLatency = 1
            d3d11.maxFrameLatency = 1
            d3d9.maxFrameLatency = 1
        """.trimIndent() + "\n"

        runCatching {
            confFile.writeText(content)
            ShellLog.info(context, "Created optimized dxvk.conf at ${confFile.absolutePath}")
        }.onFailure { error ->
            ShellLog.error(context, "Failed to write dxvk.conf", error)
        }
        return confFile
    }
}

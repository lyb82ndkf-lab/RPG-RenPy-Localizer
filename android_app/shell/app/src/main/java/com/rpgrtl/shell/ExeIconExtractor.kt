package com.rpgrtl.shell

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Base64
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Best-effort extraction of the primary icon from a Windows PE (.exe).
 * Returns a data-URL PNG, or empty string on failure.
 */
object ExeIconExtractor {
    fun extractDataUrl(context: Context, uri: Uri, maxSide: Int = 96): String {
        return runCatching {
            val name = uri.lastPathSegment.orEmpty().lowercase()
            // Direct image files
            if (name.endsWith(".png") || name.endsWith(".jpg") || name.endsWith(".jpeg") ||
                name.endsWith(".webp") || name.endsWith(".gif") || name.endsWith(".ico")
            ) {
                val img = extractImageDataUrl(context, uri, maxSide)
                if (img.isNotBlank()) return img
            }
            val bytes = readBytesCapped(context, uri, 16 * 1024 * 1024) ?: return ""
            // PNG/JPEG magic even without extension
            if (bytes.size > 8 && bytes[0] == 0x89.toByte() && bytes[1] == 'P'.code.toByte()) {
                val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return ""
                return bitmapToDataUrl(scaleDown(bmp, maxSide))
            }
            val ico = extractLargestIcoFromPe(bytes)
            if (ico != null) {
                val bmp = decodeIcoToBitmap(ico, maxSide)
                if (bmp != null) return bitmapToDataUrl(bmp)
            }
            // Last resort: scan PE for embedded PNG
            val png = findEmbeddedPng(bytes)
            if (png != null) {
                val bmp = BitmapFactory.decodeByteArray(png, 0, png.size)
                if (bmp != null) return bitmapToDataUrl(scaleDown(bmp, maxSide))
            }
            ""
        }.getOrDefault("")
    }

    /** Decode a plain image URI (png/jpg/webp/ico) to data-URL. */
    fun extractImageDataUrl(context: Context, uri: Uri, maxSide: Int = 96): String {
        return runCatching {
            val bytes = readBytesCapped(context, uri, 4 * 1024 * 1024) ?: return ""
            // Try ICO container first when magic matches
            if (bytes.size >= 6 && u16(bytes, 2) == 1) {
                decodeIcoToBitmap(bytes, maxSide)?.let { return bitmapToDataUrl(it) }
            }
            val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
            var sample = 1
            val w = opts.outWidth
            val h = opts.outHeight
            while (w / sample > maxSide * 2 || h / sample > maxSide * 2) sample *= 2
            val decode = BitmapFactory.Options().apply { inSampleSize = sample }
            val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, decode) ?: return ""
            bitmapToDataUrl(scaleDown(bmp, maxSide))
        }.getOrDefault("")
    }

    private fun readBytesCapped(context: Context, uri: Uri, cap: Int): ByteArray? {
        return context.contentResolver.openInputStream(uri)?.use { input ->
            val buf = ByteArrayOutputStream()
            val chunk = ByteArray(64 * 1024)
            var total = 0
            while (total < cap) {
                val n = input.read(chunk)
                if (n <= 0) break
                buf.write(chunk, 0, n)
                total += n
            }
            buf.toByteArray()
        }
    }

    private fun bitmapToDataUrl(bmp: Bitmap): String {
        val out = ByteArrayOutputStream()
        bmp.compress(Bitmap.CompressFormat.PNG, 92, out)
        return "data:image/png;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
    }

    private fun findEmbeddedPng(pe: ByteArray): ByteArray? {
        // Look for PNG signatures inside PE (common for some packers / resources)
        val sig = byteArrayOf(0x89.toByte(), 'P'.code.toByte(), 'N'.code.toByte(), 'G'.code.toByte())
        var i = 0
        var best: ByteArray? = null
        while (i < pe.size - 24) {
            if (pe[i] == sig[0] && pe[i + 1] == sig[1] && pe[i + 2] == sig[2] && pe[i + 3] == sig[3]) {
                // Find IEND
                var j = i + 8
                var found = -1
                while (j < pe.size - 8 && j - i < 2 * 1024 * 1024) {
                    if (pe[j] == 'I'.code.toByte() && pe[j + 1] == 'E'.code.toByte() &&
                        pe[j + 2] == 'N'.code.toByte() && pe[j + 3] == 'D'.code.toByte()
                    ) {
                        found = j + 8
                        break
                    }
                    j++
                }
                if (found > i) {
                    val slice = pe.copyOfRange(i, found)
                    if (best == null || slice.size > best!!.size) best = slice
                    i = found
                    continue
                }
            }
            i++
        }
        return best
    }

    private fun extractLargestIcoFromPe(pe: ByteArray): ByteArray? {
        if (pe.size < 64) return null
        // DOS header
        if (pe[0] != 'M'.code.toByte() || pe[1] != 'Z'.code.toByte()) return null
        val eLfanew = u32(pe, 0x3C)
        if (eLfanew + 24 >= pe.size) return null
        if (pe[eLfanew] != 'P'.code.toByte() || pe[eLfanew + 1] != 'E'.code.toByte()) return null
        val coff = eLfanew + 4
        val numSections = u16(pe, coff + 2)
        val sizeOfOptionalHeader = u16(pe, coff + 16)
        val opt = coff + 20
        if (opt + sizeOfOptionalHeader > pe.size) return null
        val magic = u16(pe, opt)
        val isPe32Plus = magic == 0x20B
        val dataDirOff = if (isPe32Plus) opt + 112 else opt + 96
        if (dataDirOff + 16 > pe.size) return null
        // Resource directory is entry #2
        val resRva = u32(pe, dataDirOff + 16)
        val resSize = u32(pe, dataDirOff + 20)
        if (resRva == 0 || resSize == 0) return null

        val sections = ArrayList<Section>(numSections)
        val sectionTable = opt + sizeOfOptionalHeader
        for (i in 0 until numSections) {
            val off = sectionTable + i * 40
            if (off + 40 > pe.size) break
            sections.add(
                Section(
                    virtualAddress = u32(pe, off + 12),
                    sizeOfRawData = u32(pe, off + 16),
                    pointerToRawData = u32(pe, off + 20)
                )
            )
        }

        fun rvaToOff(rva: Int): Int {
            for (s in sections) {
                if (rva >= s.virtualAddress && rva < s.virtualAddress + maxOf(s.sizeOfRawData, 1)) {
                    return s.pointerToRawData + (rva - s.virtualAddress)
                }
            }
            return -1
        }

        val resRoot = rvaToOff(resRva)
        if (resRoot < 0) return null

        // Type level: find RT_GROUP_ICON (14) or RT_ICON (3)
        val groupIconEntries = findResourceLeaves(pe, resRoot, resRva, ::rvaToOff, targetType = 14)
        val iconEntries = findResourceLeaves(pe, resRoot, resRva, ::rvaToOff, targetType = 3)
        if (groupIconEntries.isEmpty() && iconEntries.isEmpty()) return null

        // Prefer building ICO from GROUP_ICON + ICON entries
        if (groupIconEntries.isNotEmpty()) {
            val groupData = readResourceData(pe, groupIconEntries.maxByOrNull { it.size }!!, ::rvaToOff)
                ?: return null
            return buildIcoFromGroup(pe, groupData, iconEntries, ::rvaToOff)
        }

        // Fallback: single RT_ICON blob wrapped as ICO
        val best = iconEntries.maxByOrNull { it.size } ?: return null
        val data = readResourceData(pe, best, ::rvaToOff) ?: return null
        return wrapSingleIconAsIco(data)
    }

    private data class Section(val virtualAddress: Int, val sizeOfRawData: Int, val pointerToRawData: Int)
    private data class ResLeaf(val dataRva: Int, val size: Int, val nameId: Int = -1)

    private fun findResourceLeaves(
        pe: ByteArray,
        dirOff: Int,
        resRva: Int,
        rvaToOff: (Int) -> Int,
        targetType: Int
    ): List<ResLeaf> {
        val out = ArrayList<ResLeaf>()
        walkDir(pe, dirOff, resRva, rvaToOff, 0, targetType, -1, -1, out)
        return out
    }

    private fun walkDir(
        pe: ByteArray,
        dirOff: Int,
        resRva: Int,
        rvaToOff: (Int) -> Int,
        depth: Int,
        targetType: Int,
        currentType: Int,
        currentNameId: Int,
        out: MutableList<ResLeaf>
    ) {
        if (dirOff < 0 || dirOff + 16 > pe.size || depth > 4) return
        val named = u16(pe, dirOff + 12)
        val idCount = u16(pe, dirOff + 14)
        val total = named + idCount
        for (i in 0 until total) {
            val entryOff = dirOff + 16 + i * 8
            if (entryOff + 8 > pe.size) break
            val nameOrId = u32(pe, entryOff)
            val offsetToData = u32(pe, entryOff + 4)
            val isDir = (offsetToData and 0x80000000.toInt()) != 0
            val childRva = offsetToData and 0x7FFFFFFF
            val childOff = rvaToOff(resRva + childRva)
            val id = if ((nameOrId and 0x80000000.toInt()) == 0) nameOrId else -1
            val nextType = if (depth == 0) id else currentType
            val nextName = if (depth == 1) id else currentNameId
            if (depth == 0 && targetType >= 0 && id != targetType) continue
            if (isDir) {
                walkDir(pe, childOff, resRva, rvaToOff, depth + 1, targetType, nextType, nextName, out)
            } else {
                if (childOff < 0 || childOff + 16 > pe.size) continue
                val dataRva = u32(pe, childOff)
                val size = u32(pe, childOff + 4)
                if (size > 0 && size < 4 * 1024 * 1024) {
                    out.add(ResLeaf(dataRva, size, currentNameId))
                }
            }
        }
    }

    private fun readResourceData(pe: ByteArray, leaf: ResLeaf, rvaToOff: (Int) -> Int): ByteArray? {
        val off = rvaToOff(leaf.dataRva)
        if (off < 0 || off + leaf.size > pe.size) return null
        return pe.copyOfRange(off, off + leaf.size)
    }

    private fun buildIcoFromGroup(
        pe: ByteArray,
        group: ByteArray,
        iconLeaves: List<ResLeaf>,
        rvaToOff: (Int) -> Int
    ): ByteArray? {
        if (group.size < 6) return null
        val count = u16(group, 4)
        if (count <= 0 || count > 64) return null
        val images = ArrayList<ByteArray>(count)
        val entries = ArrayList<ByteArray>(count)
        var imageOffset = 6 + count * 16
        for (i in 0 until count) {
            val e = 6 + i * 14
            if (e + 14 > group.size) break
            val width = group[e].toInt() and 0xFF
            val height = group[e + 1].toInt() and 0xFF
            val colorCount = group[e + 2].toInt() and 0xFF
            val planes = u16(group, e + 4)
            val bitCount = u16(group, e + 6)
            val bytesInRes = u32(group, e + 8)
            val iconId = u16(group, e + 12)
            // Match RT_ICON by resource id, then size, then largest
            val leaf = iconLeaves.firstOrNull { it.nameId == iconId }
                ?: iconLeaves.firstOrNull { it.size == bytesInRes }
                ?: iconLeaves.maxByOrNull { it.size }
                ?: continue
            val img = readResourceData(pe, leaf, rvaToOff) ?: continue
            val entry = ByteArray(16)
            entry[0] = width.toByte()
            entry[1] = height.toByte()
            entry[2] = colorCount.toByte()
            entry[3] = 0
            putU16(entry, 4, planes)
            putU16(entry, 6, bitCount)
            putU32(entry, 8, img.size)
            putU32(entry, 12, imageOffset)
            entries.add(entry)
            images.add(img)
            imageOffset += img.size
        }
        if (images.isEmpty()) return null
        val out = ByteArrayOutputStream()
        // ICONDIR
        out.write(byteArrayOf(0, 0, 1, 0))
        val cnt = ByteArray(2)
        putU16(cnt, 0, images.size)
        out.write(cnt)
        entries.forEach { out.write(it) }
        images.forEach { out.write(it) }
        return out.toByteArray()
    }

    private fun wrapSingleIconAsIco(image: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf(0, 0, 1, 0, 1, 0))
        val entry = ByteArray(16)
        entry[0] = 0 // 0 => 256
        entry[1] = 0
        putU16(entry, 4, 1)
        putU16(entry, 6, 32)
        putU32(entry, 8, image.size)
        putU32(entry, 12, 22)
        out.write(entry)
        out.write(image)
        return out.toByteArray()
    }

    private fun decodeIcoToBitmap(ico: ByteArray, maxSide: Int): Bitmap? {
        // Manual ICO: pick largest entry (PNG-compressed or DIB)
        if (ico.size >= 6 && u16(ico, 2) == 1) {
            val count = u16(ico, 4)
            if (count > 0) {
                var bestOff = -1
                var bestSize = 0
                var bestDim = 0
                for (i in 0 until count) {
                    val e = 6 + i * 16
                    if (e + 16 > ico.size) break
                    val w = ico[e].toInt() and 0xFF
                    val h = ico[e + 1].toInt() and 0xFF
                    val dim = (if (w == 0) 256 else w) * (if (h == 0) 256 else h)
                    val size = u32(ico, e + 8)
                    val off = u32(ico, e + 12)
                    if (size > 0 && off >= 0 && off + size <= ico.size && dim >= bestDim) {
                        bestDim = dim
                        bestSize = size
                        bestOff = off
                    }
                }
                if (bestOff >= 0) {
                    val slice = ico.copyOfRange(bestOff, bestOff + bestSize)
                    // PNG-compressed icon image
                    if (slice.size > 8 && slice[0] == 0x89.toByte() && slice[1] == 'P'.code.toByte()) {
                        val bmp = BitmapFactory.decodeByteArray(slice, 0, slice.size)
                        if (bmp != null) return scaleDown(bmp, maxSide)
                    }
                    // Try Android decoder on whole ICO
                    val whole = BitmapFactory.decodeByteArray(ico, 0, ico.size)
                    if (whole != null) return scaleDown(whole, maxSide)
                    // Try DIB/BMP path: prepend BITMAPFILEHEADER is hard; try direct decode
                    val dib = BitmapFactory.decodeByteArray(slice, 0, slice.size)
                    if (dib != null) return scaleDown(dib, maxSide)
                }
            }
        }
        // Prefer Android's decoder for PNG-compressed icons inside ICO
        val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(ico, 0, ico.size, opts)
        if (opts.outWidth > 0 && opts.outHeight > 0) {
            var sample = 1
            while (opts.outWidth / sample > maxSide * 2 || opts.outHeight / sample > maxSide * 2) sample *= 2
            val decode = BitmapFactory.Options().apply { inSampleSize = sample }
            val bmp = BitmapFactory.decodeByteArray(ico, 0, ico.size, decode) ?: return null
            return scaleDown(bmp, maxSide)
        }
        return null
    }

    private fun scaleDown(src: Bitmap, maxSide: Int): Bitmap {
        val w = src.width
        val h = src.height
        val scale = minOf(1f, maxSide.toFloat() / maxOf(w, h))
        if (scale >= 0.99f) return src
        return Bitmap.createScaledBitmap(src, (w * scale).toInt().coerceAtLeast(1), (h * scale).toInt().coerceAtLeast(1), true)
    }

    private fun u16(b: ByteArray, off: Int): Int {
        if (off + 2 > b.size) return 0
        return ByteBuffer.wrap(b, off, 2).order(ByteOrder.LITTLE_ENDIAN).short.toInt() and 0xFFFF
    }

    private fun u32(b: ByteArray, off: Int): Int {
        if (off + 4 > b.size) return 0
        return ByteBuffer.wrap(b, off, 4).order(ByteOrder.LITTLE_ENDIAN).int
    }

    private fun putU16(b: ByteArray, off: Int, v: Int) {
        b[off] = (v and 0xFF).toByte()
        b[off + 1] = ((v shr 8) and 0xFF).toByte()
    }

    private fun putU32(b: ByteArray, off: Int, v: Int) {
        b[off] = (v and 0xFF).toByte()
        b[off + 1] = ((v shr 8) and 0xFF).toByte()
        b[off + 2] = ((v shr 16) and 0xFF).toByte()
        b[off + 3] = ((v shr 24) and 0xFF).toByte()
    }
}

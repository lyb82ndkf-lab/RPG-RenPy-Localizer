package com.rpgrtl.shell.wine

import android.content.Context
import com.rpgrtl.shell.AndroidAiTranslationService
import com.rpgrtl.shell.MainActivity
import com.rpgrtl.shell.ShellLog
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.Collections
import java.util.ArrayDeque
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.LinkedBlockingDeque
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * Host side of the Ren'Py live translation bridge.
 *
 * Wine and Android share the process network namespace, so the injected Ren'Py
 * script can exchange text with this localhost server without copying the game.
 */
class RenPyLiveTranslationService(
    private val context: Context,
    private val projectRoot: File,
) {
    private val running = AtomicBoolean(false)
    private val translations = ConcurrentHashMap<String, String>()
    private val queued = Collections.newSetFromMap(ConcurrentHashMap<String, Boolean>())
    private val failedUntil = ConcurrentHashMap<String, Long>()
    private val queue = LinkedBlockingDeque<String>()
    private val recentLog = ArrayDeque<String>()
    private val recentLogLastAt = ConcurrentHashMap<String, Long>()
    private val captured = AtomicInteger(0)
    private val translated = AtomicInteger(0)
    private val failures = AtomicInteger(0)
    private val notifySeq = AtomicInteger(0)
    private val workspace = File(projectRoot, ".rpgrtl_workspace")
    private val cacheFile = File(workspace, "renpy_live_translation.json")
    private var serverSocket: ServerSocket? = null
    private var acceptThread: Thread? = null
    private var dispatcherThread: Thread? = null
    private var workerPool: ExecutorService? = null
    private val inFlight = AtomicInteger(0)
    private val inFlightSources = Collections.newSetFromMap(ConcurrentHashMap<String, Boolean>())
    @Volatile private var connected = false
    @Volatile private var message = "正在准备 Ren'Py 实时翻译"
    @Volatile private var lastLoggedError = ""
    @Volatile private var globalCooldownUntil = 0L
    @Volatile private var lastActiveSource = ""
    @Volatile private var forceText = ""
    @Volatile private var forceSource = ""
    @Volatile private var forceSeq = 0
    private val serverId = java.util.UUID.randomUUID().toString()

    fun installAndStart(): Boolean {
        val scriptsDir = File(projectRoot, "game")
        if (!isRenPyProject(scriptsDir)) return false
        if (!liveTranslationEnabled()) {
            updateStatus("Ren'Py AI 实时翻译已关闭")
            return false
        }
        return runCatching {
            workspace.mkdirs()
            loadCache()
            installBridge(scriptsDir)
            synchronized(COMPANION_LOCK) {
                active?.takeIf { it !== this }?.stop()
                active = this
            }
            startServer()
            startTranslationWorker()
            updateStatus("实时翻译已就绪，等待游戏文本")
            ShellLog.info(context, "RenPy live translation ready cache=${translations.size}")
            true
        }.getOrElse { error ->
            stop()
            failures.incrementAndGet()
            updateStatus("实时翻译初始化失败：${error.message}")
            ShellLog.error(context, "RenPy live translation init failed", error)
            false
        }
    }

    fun stop() {
        if (!running.compareAndSet(true, false)) return
        runCatching { serverSocket?.close() }
        acceptThread?.interrupt()
        dispatcherThread?.interrupt()
        workerPool?.shutdownNow()
        workerPool = null
        inFlight.set(0)
        inFlightSources.clear()
        updateStatus("Ren'Py 实时翻译已停止")
        synchronized(COMPANION_LOCK) {
            if (active === this) active = null
        }
    }

    private fun isRenPyProject(scriptsDir: File): Boolean {
        if (!scriptsDir.isDirectory) return false
        if (File(projectRoot, "renpy").isDirectory) return true
        return scriptsDir.listFiles()?.any {
            it.isFile && (it.extension.equals("rpy", true) || it.extension.equals("rpyc", true))
        } == true
    }

    private fun liveTranslationEnabled(): Boolean {
        val raw = preferences().getString("launch_settings_json", "").orEmpty()
        if (raw.isBlank()) return true
        return runCatching {
            val root = JSONObject(raw)
            val renpy = root.optJSONObject("game")?.optJSONObject("renpy")
                ?: root.optJSONObject("renpy")
                ?: JSONObject()
            renpy.optBoolean("liveTranslation", true)
        }.getOrDefault(true)
    }

    private fun installBridge(scriptsDir: File) {
        val destination = File(scriptsDir, BRIDGE_NAME)
        val source = context.assets.open("renpy/$BRIDGE_NAME").bufferedReader(Charsets.UTF_8).use { it.readText() }
        val old = destination.takeIf { it.isFile }?.readText(Charsets.UTF_8).orEmpty()
        if (old != source) {
            destination.writeText(source, Charsets.UTF_8)
            File(scriptsDir, BRIDGE_NAME.removeSuffix(".rpy") + ".rpyc").delete()
        }
        injectSystemCjkFont(scriptsDir)
    }

    private fun injectSystemCjkFont(scriptsDir: File) {
        runCatching {
            val candidates = listOf(
                "/system/fonts/NotoSansSC-Regular.otf",
                "/system/fonts/NotoSansCJK-Regular.ttc",
                "/system/fonts/SourceHanSansCN-Regular.otf",
                "/system/fonts/DroidSansFallback.ttf",
                "/system/fonts/MiSans-Regular.ttf",
                "/system/fonts/OPPOSans-Regular.ttf",
                "/system/fonts/HarmonyOS_Sans_SC.ttf"
            )
            val found = candidates.map { File(it) }.firstOrNull { it.isFile && it.length() > 300_000 }
            if (found != null) {
                val targetFontsDir = File(scriptsDir, "fonts").apply { mkdirs() }
                val targetFont = File(targetFontsDir, "RPGRenPyLocalizerCJK.ttf")
                if (!targetFont.isFile || targetFont.length() != found.length()) {
                    found.copyTo(targetFont, overwrite = true)
                    ShellLog.info(context, "RenPy CJK font injected from ${found.absolutePath} size=${targetFont.length()}")
                }
                val overrideRpy = File(scriptsDir, "zz_rpgrtl_font_override.rpy")
                val overrideContent = """
                    # Auto-generated by RPGRenPyLocalizer
                    init 999 python:
                        _rpgrtl_live_cjk_font = "fonts/RPGRenPyLocalizerCJK.ttf"
                        if renpy.loadable(_rpgrtl_live_cjk_font):
                            try:
                                gui.text_font = _rpgrtl_live_cjk_font
                                gui.name_text_font = _rpgrtl_live_cjk_font
                                gui.interface_text_font = _rpgrtl_live_cjk_font
                            except Exception:
                                pass
                            for _rpgrtl_style_name in ('default', 'say_dialogue', 'say_label', 'choice_button_text', 'button_text', 'input', 'textbutton_text'):
                                try:
                                    getattr(style, _rpgrtl_style_name).font = _rpgrtl_live_cjk_font
                                except Exception:
                                    pass
                """.trimIndent()
                val old = overrideRpy.takeIf { it.isFile }?.readText(Charsets.UTF_8).orEmpty()
                if (old != overrideContent) {
                    overrideRpy.writeText(overrideContent, Charsets.UTF_8)
                    File(scriptsDir, "zz_rpgrtl_font_override.rpyc").delete()
                }
            }
        }.onFailure {
            ShellLog.error(context, "RenPy CJK font injection failed", it)
        }
    }

    private fun startServer() {
        if (!running.compareAndSet(false, true)) return
        val socket = ServerSocket()
        socket.reuseAddress = true
        socket.bind(InetSocketAddress(InetAddress.getByName("127.0.0.1"), PORT))
        serverSocket = socket
        acceptThread = Thread({
            while (running.get()) {
                val client = runCatching { socket.accept() }.getOrNull() ?: break
                Thread({
                    try {
                        handleClient(client)
                    } catch (error: Throwable) {
                        ShellLog.error(context, "RenPy HTTP client crashed", error)
                    }
                }, "rpgrtl-renpy-http-client").apply {
                    isDaemon = true
                    start()
                }
            }
        }, "rpgrtl-renpy-http").apply {
            isDaemon = true
            start()
        }
    }

    private fun handleClient(socket: Socket) {
        socket.use { client ->
            client.soTimeout = 2500
            val reader = BufferedReader(InputStreamReader(client.getInputStream(), Charsets.UTF_8))
            val requestLine = reader.readLine().orEmpty()
            val path = requestLine.split(' ').getOrNull(1).orEmpty()
            var contentLength = 0
            while (true) {
                val line = reader.readLine() ?: break
                if (line.isEmpty()) break
                if (line.startsWith("Content-Length:", true)) {
                    contentLength = line.substringAfter(':').trim().toIntOrNull() ?: 0
                }
            }
            val body = if (contentLength > 0) {
                val chars = CharArray(contentLength)
                var offset = 0
                while (offset < chars.size) {
                    val count = reader.read(chars, offset, chars.size - offset)
                    if (count <= 0) break
                    offset += count
                }
                String(chars, 0, offset)
            } else "{}"
            val payload = runCatching { JSONObject(body) }.getOrDefault(JSONObject())
            val response = when (path.substringBefore('?')) {
                "/translation_batch", "/pre_translate" -> translationBatch(payload)
                "/pull" -> JSONObject()
                    .put("ok", true)
                    .put("translations", JSONObject(translations as Map<*, *>))
                    .put("count", translations.size)
                    .put("seq", notifySeq.get())
                    .put("server_id", serverId)
                "/boot" -> {
                    connected = true
                    val gamedir = payload.optString("root").ifBlank { projectRoot.absolutePath }
                    updateStatus("Hook 已连接，等待游戏文本")
                    addRecentLog("Hook connected gamedir=$gamedir")
                    ShellLog.info(context, "RenPy bridge boot gamedir=$gamedir cache=${translations.size} server=$serverId")
                    JSONObject()
                        .put("ok", true)
                        .put("notify_seq", notifySeq.get())
                        .put("seq", notifySeq.get())
                        .put("server_id", serverId)
                        .put("translation_count", translations.size)
                }
                "/notify" -> {
                    val forced = forceText
                    val fSource = forceSource
                    val fseq = forceSeq
                    // Deliver once; bridge keeps force_text only when source still matches active line.
                    if (forced.isNotBlank()) {
                        forceText = ""
                        forceSource = ""
                    }
                    JSONObject()
                        .put("ok", true)
                        .put("notify_seq", notifySeq.get())
                        .put("seq", notifySeq.get())
                        .put("force_seq", fseq)
                        .put("server_id", serverId)
                        .put("translation_count", translations.size)
                        .put("translations", JSONObject(translations as Map<*, *>))
                        .put("force_text", forced)
                        .put("force_source", fSource)
                        .put("inflight", inFlight.get())
                        .put("queue", queue.size)
                }
                "/seen" -> {
                    val source = payload.optString("what").ifBlank { payload.optString("source") }.trim()
                    val displayed = payload.optString("displayed").ifBlank { source }.trim()
                    val kind = payload.optString("event").ifBlank { payload.optString("kind") }
                    if (source.isNotBlank() && (kind.contains("say") || kind.contains("display") || kind.isBlank())) {
                        lastActiveSource = source
                    }
                    val target = payload.optString("target").ifBlank {
                        lookupCached(source) ?: lookupCached(displayed).orEmpty()
                    }
                    logSeenEvent(payload.put("matched", target.isNotBlank()))
                    if (source.isNotBlank() && target.isBlank() && isTranslatable(source)) {
                        enqueueSource(source, prioritize = true)
                    }
                    JSONObject()
                        .put("ok", true)
                        .put("target", target)
                        .put("seq", notifySeq.get())
                        .put("server_id", serverId)
                }
                "/seen_batch" -> seenBatch(payload)
                "/log" -> {
                    logBridgeEvent(payload)
                    JSONObject()
                        .put("ok", true)
                        .put("seq", notifySeq.get())
                        .put("server_id", serverId)
                }
                else -> JSONObject().put("ok", true).put("seq", notifySeq.get())
            }
            val bytes = response.toString().toByteArray(Charsets.UTF_8)
            client.getOutputStream().apply {
                write("HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.US_ASCII))
                write(bytes)
                flush()
            }
        }
    }

    private fun seenBatch(payload: JSONObject): JSONObject {
        connected = true
        val items = payload.optJSONArray("items") ?: JSONArray()
        val targets = JSONArray()
        var matched = 0
        var enqueued = 0
        for (i in 0 until items.length()) {
            val item = items.optJSONObject(i)
            if (item == null) {
                targets.put("")
                continue
            }
            val source = item.optString("what").ifBlank { item.optString("source") }.trim()
            val displayed = item.optString("displayed").ifBlank { source }.trim()
            var target = item.optString("target").trim()
            if (target.isBlank()) {
                target = lookupCached(source) ?: lookupCached(displayed).orEmpty()
            }
            targets.put(target)
            if (target.isNotBlank()) matched++
            if (source.isNotBlank()) {
                val kind = item.optString("event").ifBlank { item.optString("kind") }
                if (kind.contains("say") || kind.contains("display") || kind.contains("text") || kind.isBlank()) {
                    lastActiveSource = source
                }
            }
            if (source.isNotBlank() && target.isBlank() && isTranslatable(source) && enqueueSource(source, prioritize = true)) {
                enqueued++
            }
        }
        if (items.length() > 0) {
            addRecentLog("seen batch: ${items.length()} matched=$matched queue+$enqueued")
        }
        updateStatus(message)
        return JSONObject()
            .put("ok", true)
            .put("seq", notifySeq.get())
            .put("server_id", serverId)
            .put("targets", targets)
    }

    private fun translationBatch(payload: JSONObject): JSONObject {
        connected = true
        val requested = payload.optJSONArray("texts") ?: JSONArray()
        val hits = JSONObject()
        var enqueued = 0
        for (index in 0 until minOf(requested.length(), MAX_BATCH_REQUEST_TEXTS)) {
            val source = requested.optString(index).trim()
            if (source.isBlank()) continue
            val cached = lookupCached(source)
            if (cached != null) {
                hits.put(source, cached)
                continue
            }
            val prioritize = source == lastActiveSource
            if (enqueueSource(source, prioritize = prioritize)) enqueued++
        }
        updateStatus(
            when {
                hits.length() > 0 -> "实时替换 ${hits.length()} 条文本"
                enqueued > 0 || queue.isNotEmpty() -> "已捕获 ${captured.get()} 条，等待 AI 翻译（队列 ${queue.size}）"
                else -> message
            }
        )
        return JSONObject()
            .put("ok", true)
            .put("translations", hits)
            .put("queued", enqueued)
            .put("notify_seq", notifySeq.get())
            .put("seq", notifySeq.get())
            .put("server_id", serverId)
            .put("translation_count", translations.size)
    }

    private fun enqueueSource(source: String, prioritize: Boolean = false): Boolean {
        val text = source.trim()
        if (text.isBlank() || !isTranslatable(text)) return false
        if (lookupCached(text) != null) return false
        val now = System.currentTimeMillis()
        if (globalCooldownUntil > now) return false
        if (queue.size >= MAX_PENDING_QUEUE) return false
        // Ordinary look-ahead entries use failure cooldown. The line currently
        // visible to the player must not be held behind that cooldown.
        if (!prioritize && (failedUntil[text] ?: 0L) > now) return false
        if (!queued.add(text)) {
            // Already queued: optionally bubble active line to front by re-offer after drain.
            return false
        }
        captured.incrementAndGet()
        if (prioritize) queue.offerFirst(text) else queue.offer(text)
        addRecentLog("capture${if (prioritize) "!" else ""}: ${text.take(80)}")
        return true
    }

    private fun logSeenEvent(payload: JSONObject) {
        val source = payload.optString("what").ifBlank { payload.optString("source") }
        if (source.isNotBlank()) {
            val matched = payload.optBoolean("matched", false)
            addRecentLog("seen${if (matched) " matched" else ""}: ${source.take(80)}")
            updateStatus(message)
        }
    }

    private fun logBridgeEvent(payload: JSONObject) {
        val event = payload.optString("event", "bridge")
        val data = payload.optJSONObject("payload") ?: JSONObject()
        val source = data.optString("source")
            .ifBlank { data.optString("what") }
            .ifBlank { data.optString("target") }
        val detail = when {
            source.isNotBlank() -> "$event: ${source.take(80)}"
            data.has("count") -> "$event count=${data.optInt("count") }"
            else -> event
        }
        addRecentLog("bridge $detail")
        updateStatus(message)
    }

    private fun startTranslationWorker() {
        // The dispatcher reads the saved setting for every wave. Retain the
        // maximum physical pool so UI changes can increase concurrency without
        // restarting the game.
        workerPool = Executors.newFixedThreadPool(MAX_CONCURRENCY) { r ->
            Thread(r, "rpgrtl-renpy-ai-worker").apply { isDaemon = true }
        }
        dispatcherThread = Thread({
            while (running.get()) {
                try {
                    if (globalCooldownUntil > System.currentTimeMillis()) {
                        Thread.sleep(200)
                        continue
                    }
                    if (queue.isEmpty()) {
                        Thread.sleep(40)
                        continue
                    }
                    val pool = workerPool ?: break
                    val cfg = try {
                        loadAiSettings()
                    } catch (_: Throwable) {
                        Thread.sleep(500)
                        continue
                    }
                    val maxWorkers = cfg.optInt("concurrency", DEFAULT_CONCURRENCY).coerceIn(1, MAX_CONCURRENCY)
                    // Fill free worker slots while queue has work.
                    while (running.get() && inFlight.get() < maxWorkers && queue.isNotEmpty()) {
                        val batch = takeNextBatch(cfg)
                        if (batch.isEmpty()) break
                        batch.forEach { inFlightSources.add(it) }
                        inFlight.incrementAndGet()
                        val jobId = inFlight.get()
                        addRecentLog(
                            "AI batch#$jobId: ${batch.size} texts " +
                                "(q=${queue.size} fly=${inFlight.get()}/$maxWorkers)"
                        )
                        updateStatus(
                            "AI 并发 ${inFlight.get()}/$maxWorkers · 本批 ${batch.size} · 队列 ${queue.size}"
                        )
                        pool.execute {
                            try {
                                runAiJob(cfg, batch)
                            } finally {
                                batch.forEach {
                                    inFlightSources.remove(it)
                                    queued.remove(it)
                                }
                                inFlight.decrementAndGet()
                            }
                        }
                        // Tiny stagger reduces provider burst 429 while keeping concurrency.
                        val gap = cfg.optLong("requestIntervalMs", 80L).coerceIn(0L, 1_500L)
                        if (gap > 0 && inFlight.get() < maxWorkers && queue.isNotEmpty()) {
                            Thread.sleep(minOf(gap, 120L))
                        }
                    }
                    Thread.sleep(30)
                } catch (error: InterruptedException) {
                    break
                } catch (error: Throwable) {
                    if (!running.get()) break
                    addRecentLog("dispatch error: ${(error.message ?: error.javaClass.simpleName).take(80)}")
                    try {
                        Thread.sleep(300)
                    } catch (_: InterruptedException) {
                        break
                    }
                }
            }
        }, "rpgrtl-renpy-ai-dispatch").apply {
            isDaemon = true
            start()
        }
        addRecentLog("AI pool ready maxConcurrency=$MAX_CONCURRENCY")
    }

    /**
     * Dual-lane drain:
     * - Express: current on-screen line first, tiny accumulate, small batch → fast replace
     * - Bulk: drain remaining queue up to large batch for prefetch
     */
    private fun takeNextBatch(settings: JSONObject): List<String> {
        val active = lastActiveSource.trim()
        val configuredBatchSize = settings.optInt("batchSize", DEFAULT_BULK_BATCH)
            .coerceIn(1, MAX_AI_BATCH_SIZE)
        // Prefer active line as express job if sitting in queue and not already in-flight.
        if (active.isNotBlank() && active !in inFlightSources && queue.remove(active)) {
            val express = ArrayList<String>(configuredBatchSize)
            acceptInto(express, active)
            // Very short window to grab 1–2 nearby captures with the current line.
            try {
                Thread.sleep(EXPRESS_ACCUMULATE_MS)
            } catch (_: InterruptedException) {
                return express
            }
            while (express.size < configuredBatchSize) {
                val next = queue.poll() ?: break
                if (next in inFlightSources) continue
                acceptInto(express, next)
            }
            if (express.isNotEmpty()) return express
        }

        val bulkSize = configuredBatchSize
        val first = queue.poll() ?: return emptyList()
        if (first in inFlightSources) return takeNextBatch(settings)
        val bulk = ArrayList<String>(bulkSize)
        acceptInto(bulk, first)
        try {
            Thread.sleep(BULK_ACCUMULATE_MS)
        } catch (_: InterruptedException) {
            return bulk
        }
        // If active arrived during accumulate, put it first in this bulk.
        if (active.isNotBlank() && active !in inFlightSources && queue.remove(active)) {
            acceptInto(bulk, active)
            if (bulk.size > 1 && bulk.first() != active && bulk.contains(active)) {
                bulk.remove(active)
                bulk.add(0, active)
            }
        }
        while (bulk.size < bulkSize) {
            val next = queue.poll() ?: break
            if (next in inFlightSources) continue
            acceptInto(bulk, next)
        }
        return bulk
    }

    private fun acceptInto(batch: MutableList<String>, text: String) {
        val value = text.trim()
        if (value.isBlank()) {
            queued.remove(text)
            return
        }
        if (lookupCached(value) != null || !isTranslatable(value) || value in inFlightSources) {
            queued.remove(value)
            return
        }
        if (!batch.contains(value)) batch.add(value)
    }

    private fun runAiJob(settings: JSONObject, batch: List<String>) {
        try {
            val results = callAiBatch(settings, batch)
            val done = LinkedHashMap<String, String>()
            for (index in 0 until results.length()) {
                val item = results.optJSONObject(index) ?: continue
                val entryId = item.optString("entry_id")
                val source = item.optString("source").trim().ifBlank {
                    val match = Regex("""live_(\d+)""").find(entryId)
                    val idx = match?.groupValues?.getOrNull(1)?.toIntOrNull()?.minus(1)
                    if (idx != null && idx in batch.indices) batch[idx] else ""
                }
                val target = item.optString("target").trim()
                if (source.isBlank() || target.isBlank()) continue
                if (!controlTokensPreserved(source, target)) {
                    addRecentLog("AI drop tokens: ${source.take(50)}")
                    continue
                }
                if (target == source) continue
                done[source] = target
            }
            if (done.isNotEmpty()) {
                publishTranslations(done)
            }
            var missing = batch.filter { it !in done && lookupCached(it) == null }
            // A partial large-batch response must not leave the current screen
            // waiting for the normal retry cooldown. Match desktop behaviour:
            // immediately make one focused request for the visible source.
            val current = lastActiveSource.trim()
            if (current.isNotBlank() && current in missing) {
                addRecentLog("AI urgent current retry: ${current.take(60)}")
                try {
                    val urgentResults = callAiBatch(settings, listOf(current))
                    val urgent = urgentResults.optJSONObject(0)
                    val target = urgent?.optString("target")?.trim().orEmpty()
                    if (target.isNotBlank() && target != current && controlTokensPreserved(current, target)) {
                        done[current] = target
                        publishTranslations(mapOf(current to target))
                        missing = missing.filter { it != current }
                    }
                } catch (urgentError: Throwable) {
                    addRecentLog("AI urgent retry failed: ${(urgentError.message ?: urgentError.javaClass.simpleName).take(80)}")
                }
            }
            // Providers occasionally return only part of a large JSON object.
            // Repair the remainder immediately in compact chunks instead of
            // deferring every nearby line to the normal five-second cooldown.
            // Primary jobs already occupy the configured worker pool, so these
            // repairs retain the same cross-batch parallelism as desktop.
            if (missing.isNotEmpty() && batch.size > 1) {
                val repairSize = ((batch.size + 2) / 3).coerceIn(2, 20)
                addRecentLog("AI repair: ${missing.size} texts in chunks of $repairSize")
                for (repairBatch in missing.chunked(repairSize)) {
                    val repaired = runCatching { callAiBatch(settings, repairBatch) }.getOrElse { repairError ->
                        addRecentLog("AI repair failed: ${(repairError.message ?: repairError.javaClass.simpleName).take(80)}")
                        JSONArray()
                    }
                    val repairedDone = LinkedHashMap<String, String>()
                    for (index in 0 until repaired.length()) {
                        val item = repaired.optJSONObject(index) ?: continue
                        val source = item.optString("source").trim()
                        val target = item.optString("target").trim()
                        if (source.isNotBlank() && target.isNotBlank() && target != source && controlTokensPreserved(source, target)) {
                            repairedDone[source] = target
                        }
                    }
                    if (repairedDone.isNotEmpty()) {
                        done.putAll(repairedDone)
                        publishTranslations(repairedDone)
                    }
                }
                missing = batch.filter { it !in done && lookupCached(it) == null }
            }
            if (missing.isNotEmpty()) {
                scheduleRequeue(missing)
                addRecentLog("AI partial: ok=${done.size} miss=${missing.size}")
            }
            if (done.isEmpty()) {
                throw IllegalStateException("AI 没有返回可用译文 (${batch.size} 条)")
            }
        } catch (error: Throwable) {
            if (!running.get() || error is InterruptedException) return
            failures.incrementAndGet()
            val reason = error.message ?: error.javaClass.simpleName
            updateStatus("实时翻译失败：$reason")
            if (lastLoggedError != reason) {
                lastLoggedError = reason
                ShellLog.error(context, "RenPy live AI translation failed: $reason")
            }
            val rateLimited = reason.contains("429") || reason.contains("503") ||
                reason.contains("ResourceExhausted", ignoreCase = true)
            val cooldown = if (rateLimited) RATE_LIMIT_COOLDOWN_MS else RETRY_COOLDOWN_MS
            val until = System.currentTimeMillis() + cooldown
            if (rateLimited) globalCooldownUntil = until
            addRecentLog("AI failed: ${reason.take(140)}")
            batch.forEach { failedUntil[it] = until }
            scheduleRequeue(batch, delayMs = minOf(cooldown, 15_000L) + 200L)
        }
    }

    private fun callAiBatch(settings: JSONObject, batch: List<String>): JSONArray {
        val entries = JSONArray()
        batch.forEachIndexed { index, source ->
            entries.put(
                JSONObject()
                    .put("entry_id", "live_${index + 1}")
                    .put("source", source)
            )
        }
        val request = JSONObject()
            .put("settings", settings)
            .put("targetLang", settings.optString("targetLang", "简体中文"))
            .put("entries", entries)
        val response = AndroidAiTranslationService().translate(request)
        if (!response.optBoolean("ok", false)) {
            throw IllegalStateException(response.optString("error", "AI translation failed"))
        }
        return response.optJSONArray("translations") ?: JSONArray()
    }

    /** Memory merge + force ONLY if result is still the on-screen line. */
    private fun publishTranslations(done: Map<String, String>) {
        for ((source, target) in done) {
            storeTranslation(source, target)
        }
        translated.addAndGet(done.size)
        val live = lastActiveSource.trim()
        val activeTarget = when {
            live.isNotBlank() && done.containsKey(live) -> done[live].orEmpty()
            live.isNotBlank() -> lookupCached(live).orEmpty()
            else -> ""
        }
        // Never force a stale line onto a newer dialogue page.
        if (activeTarget.isNotBlank() && live.isNotBlank()) {
            forceText = activeTarget
            forceSource = live
            forceSeq += 1
            addRecentLog("force_text#$forceSeq: ${activeTarget.take(60)}")
        }
        notifySeq.incrementAndGet()
        lastLoggedError = ""
        done.entries.take(5).forEach { (src, tgt) ->
            addRecentLog("translated: ${src.take(50)} -> ${tgt.take(40)}")
        }
        if (done.size > 5) addRecentLog("batch publish: ${done.size} translations notify#${notifySeq.get()}")
        updateStatus(
            "已译 ${translated.get()} · 队列 ${queue.size} · 并发 ${inFlight.get()}"
        )
        Thread({
            runCatching { writeCache() }
        }, "rpgrtl-renpy-cache").apply { isDaemon = true; start() }
    }

    private fun scheduleRequeue(missing: List<String>, delayMs: Long = 5_000L) {
        val until = System.currentTimeMillis() + delayMs
        missing.forEach { failedUntil[it] = until }
        Thread({
            try {
                Thread.sleep(delayMs + 150L)
                missing.forEach { src ->
                    failedUntil.remove(src)
                    enqueueSource(src, prioritize = src == lastActiveSource)
                }
            } catch (_: InterruptedException) {
            }
        }, "rpgrtl-renpy-requeue").apply { isDaemon = true; start() }
    }

    private fun loadAiSettings(): JSONObject {
        val raw = preferences().getString("android_ai_settings_json", "").orEmpty()
        if (raw.isBlank()) {
            throw IllegalStateException("请先在设置页配置 AI API Key")
        }
        return JSONObject(raw).also { settings ->
            val provider = settings.optString("provider", "openai")
            if (provider != "ollama" && settings.optString("apiKey").isBlank()) {
                throw IllegalStateException("请先在设置页配置 AI API Key")
            }
        }
    }

    private fun preferences() = context.getSharedPreferences(
        MainActivity::class.java.simpleName,
        Context.MODE_PRIVATE,
    )

    private fun loadCache() {
        if (!cacheFile.isFile) return
        val raw = runCatching { JSONObject(cacheFile.readText(Charsets.UTF_8)) }.getOrNull() ?: return
        val values = raw.optJSONObject("translations") ?: return
        values.keys().forEach { source ->
            val target = values.optString(source).trim()
            if (source.isNotBlank() && target.isNotBlank()) storeTranslation(source, target)
        }
    }

    @Synchronized
    private fun writeCache() {
        workspace.mkdirs()
        val payload = JSONObject()
            .put("version", 1)
            .put("updated_at", System.currentTimeMillis())
            .put("translations", JSONObject(translations as Map<*, *>))
        val temporary = File(workspace, "${cacheFile.name}.tmp")
        temporary.writeText(payload.toString(), Charsets.UTF_8)
        if (!temporary.renameTo(cacheFile)) {
            temporary.copyTo(cacheFile, overwrite = true)
            temporary.delete()
        }
    }

    private fun updateStatus(value: String) {
        message = value
        synchronized(COMPANION_LOCK) {
            statusJson = JSONObject()
                .put("ok", true)
                .put("running", running.get())
                .put("connected", connected)
                .put("captured", captured.get())
                .put("translated", translated.get())
                .put("cached", translations.size)
                .put("failures", failures.get())
                .put("queue", queue.size)
                .put("inflight", inFlight.get())
                .put("cooldownMs", maxOf(0L, globalCooldownUntil - System.currentTimeMillis()))
                .put("recent", JSONArray(recentLogSnapshot()))
                .put("message", message)
                .put("game", projectRoot.name)
                .toString()
        }
    }

    private fun addRecentLog(line: String) {
        val key = normalizeLogKey(line)
        val now = System.currentTimeMillis()
        val lastAt = recentLogLastAt[key] ?: 0L
        if (now - lastAt < LOG_DEDUPE_MS) return
        recentLogLastAt[key] = now
        synchronized(recentLog) {
            val stamp = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.US).format(java.util.Date())
            recentLog.addLast("$stamp $line")
            while (recentLog.size > 60) recentLog.removeFirst()
            if (recentLogLastAt.size > 300) {
                recentLogLastAt.entries.removeIf { now - it.value > LOG_DEDUPE_MS }
            }
        }
    }

    private fun normalizeLogKey(line: String): String {
        val sourcePart = line.substringAfterLast(": ", line)
        return collapseWhitespace(stripRenPyTags(sourcePart)).lowercase().take(160).ifBlank { line.take(160) }
    }

    private fun recentLogSnapshot(): List<String> = synchronized(recentLog) { recentLog.toList() }

    private fun storeTranslation(source: String, target: String) {
        val cleanTarget = target.trim()
        if (source.isBlank() || cleanTarget.isBlank()) return
        for (key in translationCandidates(source)) {
            translations[key] = cleanTarget
        }
    }

    private fun translationCandidates(source: String, transformed: String? = null): List<String> {
        val values = mutableListOf(source)
        if (!transformed.isNullOrBlank() && transformed != source) values.add(0, transformed)
        val result = ArrayList<String>()
        val seen = HashSet<String>()
        for (value in values) {
            if (value.isBlank()) continue
            val stripped = value.trim()
            val plain = stripRenPyTags(stripped)
            val collapsed = collapseWhitespace(stripped)
            val plainCollapsed = collapseWhitespace(plain)
            val variants = mutableListOf(value, stripped, plain, collapsed, plainCollapsed)
            if (stripped.length >= 2 && stripped.first() == stripped.last() && (stripped.first() == '"' || stripped.first() == '\'')) {
                variants.add(stripped.substring(1, stripped.length - 1))
            }
            for (item in variants) {
                if (item.isNotBlank() && seen.add(item)) result.add(item)
            }
        }
        return result
    }

    private fun lookupCached(source: String, transformed: String? = null): String? {
        for (key in translationCandidates(source, transformed)) {
            translations[key]?.let { return it }
        }
        return null
    }

    private fun isTranslatable(source: String): Boolean {
        val plain = stripRenPyTags(source)
        if (plain.length !in 2..1200) return false
        if (plain.count { it.isLetterOrDigit() } < 2) return false
        val hasLatinOrKana = plain.any { ch ->
            val c = ch.code
            (ch.lowercaseChar() in 'a'..'z') ||
                (c in 0x3040..0x30FF) ||
                (c in 0x31F0..0x31FF) ||
                (c in 0xFF66..0xFF9D)
        }
        if (!hasLatinOrKana) return false
        val lower = plain.lowercase()
        if (lower.startsWith("http://") || lower.startsWith("https://")) return false
        if (lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".webp") || lower.endsWith(".rpy")) return false
        return true
    }

    /** Android ICU rejects several `\{...}` regex forms; strip braces manually. */
    private fun stripRenPyTags(source: String): String {
        if (source.isEmpty()) return source
        val out = StringBuilder(source.length)
        var i = 0
        while (i < source.length) {
            val ch = source[i]
            if (ch == '{') {
                val end = source.indexOf('}', i + 1)
                if (end >= 0) {
                    i = end + 1
                    continue
                }
            }
            if (ch == '[') {
                val end = source.indexOf(']', i + 1)
                if (end >= 0) {
                    i = end + 1
                    continue
                }
            }
            out.append(ch)
            i++
        }
        return out.toString().trim()
    }

    private fun collapseWhitespace(source: String): String {
        if (source.isEmpty()) return source
        val out = StringBuilder(source.length)
        var prevSpace = false
        for (ch in source) {
            val space = ch.isWhitespace()
            if (space) {
                if (!prevSpace) out.append(' ')
                prevSpace = true
            } else {
                out.append(ch)
                prevSpace = false
            }
        }
        return out.toString().trim()
    }

    private fun controlTokensPreserved(source: String, target: String): Boolean {
        return try {
            extractControlTokens(source) == extractControlTokens(target)
        } catch (_: Throwable) {
            true
        }
    }

    private fun extractControlTokens(text: String): List<String> {
        val tokens = ArrayList<String>()
        var i = 0
        while (i < text.length) {
            val ch = text[i]
            when {
                ch == '[' -> {
                    val end = text.indexOf(']', i + 1)
                    if (end >= 0) {
                        tokens.add(text.substring(i, end + 1))
                        i = end + 1
                        continue
                    }
                }
                ch == '{' -> {
                    val end = text.indexOf('}', i + 1)
                    if (end >= 0) {
                        tokens.add(text.substring(i, end + 1))
                        i = end + 1
                        continue
                    }
                }
                ch == '%' && i + 1 < text.length -> {
                    var j = i + 1
                    while (j < text.length && (text[j] == '-' || text[j] == '+' || text[j] == '.' || text[j].isDigit())) {
                        j++
                    }
                    if (j < text.length && text[j].isLetter()) {
                        tokens.add(text.substring(i, j + 1))
                        i = j + 1
                        continue
                    }
                }
            }
            i++
        }
        return tokens
    }

    companion object {
        private const val PORT = 32180
        private const val BRIDGE_NAME = "zz_rpgrtl_live_bridge.rpy"
        private const val MAX_BATCH_REQUEST_TEXTS = 300
        private const val MAX_AI_BATCH_SIZE = 200
        private const val DEFAULT_BULK_BATCH = 20
        private const val MAX_PENDING_QUEUE = 300
        private const val DEFAULT_CONCURRENCY = 3
        private const val MAX_CONCURRENCY = 8
        // Give the bridge one short full-batch window after an active line so
        // its AST look-ahead can arrive before dispatching the request.
        private const val EXPRESS_ACCUMULATE_MS = 280L
        private const val BULK_ACCUMULATE_MS = 280L
        private const val RETRY_COOLDOWN_MS = 2_500L
        private const val RATE_LIMIT_COOLDOWN_MS = 6_000L
        private const val LOG_DEDUPE_MS = 20_000L
        private val COMPANION_LOCK = Any()
        @Volatile private var active: RenPyLiveTranslationService? = null
        @Volatile private var statusJson = JSONObject()
            .put("ok", true)
            .put("running", false)
            .put("message", "尚未启动 Ren'Py 实时翻译")
            .toString()

        fun currentStatus(): String = synchronized(COMPANION_LOCK) { statusJson }
    }
}

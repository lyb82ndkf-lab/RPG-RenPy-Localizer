package com.rpgrtl.shell.wine

import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

class RuntimeBridge(private val containerId: String = "") {
    private val client = OkHttpClient.Builder()
        .connectTimeout(1200, TimeUnit.MILLISECONDS)
        .readTimeout(3, TimeUnit.SECONDS)
        .writeTimeout(3, TimeUnit.SECONDS)
        .build()
    private val requestId = AtomicInteger(1)
    private val pending = ConcurrentHashMap<Int, PendingCall>()
    @Volatile private var webSocket: WebSocket? = null
    @Volatile private var lastError = ""
    @Volatile private var connectedUrl = ""

    fun status(): JSONObject {
        val ok = ensureConnected()
        val base = JSONObject()
            .put("ok", ok)
            .put("mode", "wine-cdp")
            .put("containerId", containerId)
            .put("debugPort", CDP_PORT)
            .put("connectedUrl", connectedUrl)
            .put("error", if (ok) "" else lastError.ifBlank { "CDP is not connected. Start an MV/MZ game with remote debugging enabled." })
        if (!ok) return base
        val gameStatus = evaluate(RPG_STATUS).opt("value") as? String
        if (!gameStatus.isNullOrBlank()) {
            runCatching {
                val parsed = JSONObject(gameStatus)
                parsed.keys().forEach { key -> base.put(key, parsed.opt(key)) }
            }
        }
        return base
    }

    fun evaluate(script: String): JSONObject {
        if (!ensureConnected()) {
            return error("CDP is not connected: ${lastError.ifBlank { "port $CDP_PORT unavailable" }}")
        }
        val response = callCdp("Runtime.evaluate", JSONObject()
            .put("expression", script)
            .put("returnByValue", true)
            .put("awaitPromise", true)
            .put("userGesture", true)
        ) ?: return error(lastError.ifBlank { "Runtime.evaluate timed out" })

        val exception = response.optJSONObject("result")?.optJSONObject("exceptionDetails")
        if (exception != null) {
            return error(exception.optString("text", "JavaScript exception"))
                .put("details", exception)
        }
        return JSONObject()
            .put("ok", true)
            .put("mode", "wine-cdp")
            .put("response", response)
            .put("value", response.optJSONObject("result")
                ?.optJSONObject("result")
                ?.opt("value"))
    }

    fun command(action: String, value: String = ""): JSONObject {
        val script = when (action) {
            "status" -> RPG_STATUS
            "gold" -> "$RPG_READY && \$gameParty.gold()"
            "hp" -> "$RPG_READY && (\$gameParty.leader() ? \$gameParty.leader().hp : 0)"
            "mp" -> "$RPG_READY && (\$gameParty.leader() ? \$gameParty.leader().mp : 0)"
            "tp" -> "$RPG_READY && (\$gameParty.leader() ? \$gameParty.leader().tp : 0)"
            "setHp" -> statSetScript("hp", value.toIntOrNull() ?: 1)
            "setMp" -> statSetScript("mp", value.toIntOrNull() ?: 0)
            "setTp" -> statSetScript("tp", value.toIntOrNull() ?: 0)
            "hpLock" -> statLockScript("hp", value)
            "mpLock" -> statLockScript("mp", value)
            "tpLock" -> statLockScript("tp", value)
            "setGold" -> setGoldScript(value.toIntOrNull() ?: 0)
            "addGold" -> "$RPG_READY && \$gameParty.gainGold(${value.toIntOrNull() ?: 0}); \$gameParty.gold()"
            "recoverAll" -> "$RPG_READY && \$gameParty.members().forEach(function(a){a.recoverAll();}); true"
            "fullHeal" -> "$RPG_READY && \$gameParty.members().forEach(function(a){a.recoverAll();}); true"
            "through", "noclip" -> noClipScript(value == "true" || value == "1" || value.equals("on", true))
            "quickSave" -> "$RPG_READY && DataManager.saveGame(${value.toIntOrNull() ?: 1})"
            "battleWin" -> "$RPG_READY && typeof BattleManager !== 'undefined' && \$gameTroop.members().forEach(function(e){e._hp=0;}); BattleManager.processVictory(); true"
            "battleLose" -> "$RPG_READY && typeof BattleManager !== 'undefined' && \$gameParty.members().forEach(function(a){a._hp=0;}); BattleManager.processDefeat(); true"
            "battleEscape" -> "$RPG_READY && typeof BattleManager !== 'undefined' && BattleManager.processEscape()"
            "enemyHp1" -> "$RPG_READY && \$gameTroop.members().forEach(function(e){e._hp=1;}); true"
            "enemyHpMax" -> "$RPG_READY && \$gameTroop.members().forEach(function(e){e._hp=e.mhp;}); true"
            "partyHp1" -> "$RPG_READY && \$gameParty.members().forEach(function(a){a._hp=1;}); true"
            "partyHp0" -> "$RPG_READY && \$gameParty.members().forEach(function(a){a._hp=0;}); true"
            "openMenu" -> "typeof SceneManager !== 'undefined' && typeof Scene_Menu !== 'undefined' && SceneManager.push(Scene_Menu); true"
            "alwaysDash" -> "$RPG_READY && (\$gamePlayer._dashing = ${value == "true"}); true"
            "encounter" -> "$RPG_READY && (\$gameSystem._encounterEnabled = ${value == "true"}); true"
            "speed" -> speedScript(value.toIntOrNull() ?: 1)
            "scene" -> "typeof SceneManager !== 'undefined' && SceneManager._scene ? SceneManager._scene.constructor.name : ''"
            "variable" -> "$RPG_READY && \$gameVariables.value(${value.toIntOrNull() ?: 1})"
            "switch" -> "$RPG_READY && \$gameSwitches.value(${value.toIntOrNull() ?: 1})"
            else -> return error("Unknown runtime command: $action").put("action", action)
        }
        return evaluate(script).put("action", action)
    }

    fun setVariable(id: Int, value: Int): JSONObject {
        return evaluate("$RPG_READY && \$gameVariables.setValue($id, $value); \$gameVariables.value($id)")
            .put("action", "setVariable")
            .put("variableId", id)
    }

    fun setSwitch(id: Int, value: Boolean): JSONObject {
        return evaluate("$RPG_READY && \$gameSwitches.setValue($id, $value); \$gameSwitches.value($id)")
            .put("action", "setSwitch")
            .put("switchId", id)
    }

    fun disconnect() {
        webSocket?.close(1000, "closed")
        webSocket = null
        connectedUrl = ""
        pending.clear()
    }

    private fun ensureConnected(): Boolean {
        if (webSocket != null) return true
        val wsUrl = findDebuggerWebSocketUrl() ?: return false
        return connectWebSocket(wsUrl)
    }

    private fun findDebuggerWebSocketUrl(): String? {
        return try {
            val connection = (URL("http://127.0.0.1:$CDP_PORT/json/list").openConnection() as HttpURLConnection).apply {
                connectTimeout = 1000
                readTimeout = 1000
            }
            val body = connection.inputStream.bufferedReader().use { it.readText() }
            val pages = JSONArray(body)
            for (index in 0 until pages.length()) {
                val page = pages.optJSONObject(index) ?: continue
                val url = page.optString("webSocketDebuggerUrl")
                if (url.isNotBlank()) return url
            }
            lastError = "No debuggable NW.js page was returned by /json/list."
            null
        } catch (error: Throwable) {
            lastError = error.message ?: error.javaClass.simpleName
            null
        }
    }

    private fun connectWebSocket(wsUrl: String): Boolean {
        val latch = CountDownLatch(1)
        var opened = false
        val request = Request.Builder().url(wsUrl).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                connectedUrl = wsUrl
                opened = true
                latch.countDown()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val json = runCatching { JSONObject(text) }.getOrNull() ?: return
                val id = json.optInt("id", -1)
                if (id >= 0) pending.remove(id)?.complete(json)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                lastError = t.message ?: t.javaClass.simpleName
                this@RuntimeBridge.webSocket = null
                latch.countDown()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                this@RuntimeBridge.webSocket = null
                connectedUrl = ""
            }
        })
        latch.await(1500, TimeUnit.MILLISECONDS)
        if (!opened) {
            lastError = lastError.ifBlank { "WebSocket handshake timed out." }
            webSocket = null
        }
        return opened
    }

    private fun callCdp(method: String, params: JSONObject): JSONObject? {
        val socket = webSocket ?: return null
        val id = requestId.getAndIncrement()
        val pendingCall = PendingCall()
        pending[id] = pendingCall
        val message = JSONObject()
            .put("id", id)
            .put("method", method)
            .put("params", params)
            .toString()
        if (!socket.send(message)) {
            pending.remove(id)
            lastError = "Failed to send CDP message."
            return null
        }
        val result = pendingCall.await()
        if (result == null) {
            pending.remove(id)
            lastError = "CDP response timed out."
        }
        return result
    }

    private fun setGoldScript(value: Int): String {
        return """
            (function(){
              if (!($RPG_READY)) return false;
              var current = ${'$'}gameParty.gold();
              ${'$'}gameParty.gainGold($value - current);
              return ${'$'}gameParty.gold();
            })()
        """.trimIndent()
    }

    private fun noClipScript(enabled: Boolean): String {
        return """
            (function(){
              if (typeof Game_Player === 'undefined') return false;
              if (!Game_Player.prototype.__rpgtlCanPass) {
                Game_Player.prototype.__rpgtlCanPass = Game_Player.prototype.canPass;
              }
              if ($enabled) {
                Game_Player.prototype.canPass = function(){ return true; };
              } else {
                Game_Player.prototype.canPass = Game_Player.prototype.__rpgtlCanPass;
              }
              window.__rpgtlNoClip = $enabled;
              return window.__rpgtlNoClip;
            })()
        """.trimIndent()
    }

    private fun statLockScript(stat: String, value: String): String {
        val enabled = value != "false" && value != "0" && value.isNotBlank()
        val numeric = value.toIntOrNull() ?: when (stat) {
            "tp" -> 100
            else -> 9999
        }
        return """
            (function(){
              if (!($RPG_READY)) return false;
              window.__rpgtlLocks = window.__rpgtlLocks || {};
              window.__rpgtlLocks['$stat'] = $enabled ? $numeric : null;
              if (!window.__rpgtlLockTimer) {
                window.__rpgtlLockTimer = setInterval(function(){
                  if (!($RPG_READY)) return;
                  ${'$'}gameParty.members().forEach(function(a){
                    if (window.__rpgtlLocks.hp != null) a._hp = Math.min(a.mhp, Math.max(1, window.__rpgtlLocks.hp));
                    if (window.__rpgtlLocks.mp != null) a._mp = Math.min(a.mmp, Math.max(0, window.__rpgtlLocks.mp));
                    if (window.__rpgtlLocks.tp != null) a._tp = Math.max(0, window.__rpgtlLocks.tp);
                  });
                }, 250);
              }
              return true;
            })()
        """.trimIndent()
    }

    private fun statSetScript(stat: String, value: Int): String {
        val field = when (stat) {
            "mp" -> "_mp"
            "tp" -> "_tp"
            else -> "_hp"
        }
        val maxExpr = when (stat) {
            "mp" -> "a.mmp"
            "tp" -> "100"
            else -> "a.mhp"
        }
        val minExpr = if (stat == "hp") "1" else "0"
        return """
            (function(){
              if (!($RPG_READY)) return false;
              ${'$'}gameParty.members().forEach(function(a){
                a.$field = Math.min($maxExpr, Math.max($minExpr, $value));
              });
              return ${'$'}gameParty.leader() ? ${'$'}gameParty.leader().$field : 0;
            })()
        """.trimIndent()
    }

    private fun speedScript(value: Int): String {
        val speed = value.coerceIn(1, 16)
        return """
            (function(){
              if (typeof Scene_Map === 'undefined') return false;
              window.__rpgtlSpeed = $speed;
              if (!Scene_Map.prototype.__rpgtlUpdate) {
                Scene_Map.prototype.__rpgtlUpdate = Scene_Map.prototype.update;
                Scene_Map.prototype.update = function(){
                  var count = Math.max(1, Math.min(16, window.__rpgtlSpeed || 1));
                  for (var i = 0; i < count; i++) this.__rpgtlUpdate();
                };
              }
              return window.__rpgtlSpeed;
            })()
        """.trimIndent()
    }

    private fun error(message: String): JSONObject {
        Log.w("RuntimeBridge", message)
        return JSONObject()
            .put("ok", false)
            .put("mode", "wine-cdp")
            .put("error", message)
    }

    private class PendingCall {
        private val latch = CountDownLatch(1)
        @Volatile private var response: JSONObject? = null

        fun complete(json: JSONObject) {
            response = json
            latch.countDown()
        }

        fun await(): JSONObject? {
            latch.await(3, TimeUnit.SECONDS)
            return response
        }
    }

    companion object {
        const val CDP_PORT = 9229
        private const val RPG_READY =
            "typeof \$gameParty !== 'undefined' && typeof \$gameVariables !== 'undefined' && typeof \$gameSwitches !== 'undefined'"
        private const val RPG_STATUS =
            "JSON.stringify({ready:($RPG_READY), scene:(typeof SceneManager !== 'undefined' && SceneManager._scene ? SceneManager._scene.constructor.name : ''), gold:(typeof \$gameParty !== 'undefined' ? \$gameParty.gold() : 0), hp:(typeof \$gameParty !== 'undefined' && \$gameParty.leader() ? \$gameParty.leader().hp : 0), mp:(typeof \$gameParty !== 'undefined' && \$gameParty.leader() ? \$gameParty.leader().mp : 0), tp:(typeof \$gameParty !== 'undefined' && \$gameParty.leader() ? \$gameParty.leader().tp : 0), mapId:(typeof \$gameMap !== 'undefined' ? \$gameMap.mapId() : 0), x:(typeof \$gamePlayer !== 'undefined' ? \$gamePlayer.x : 0), y:(typeof \$gamePlayer !== 'undefined' ? \$gamePlayer.y : 0), noClip:!!window.__rpgtlNoClip})"
    }
}

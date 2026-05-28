# 修复与功能提示词（给 Codex）

---

## 致命 Bug：存档位置指向错误

### 症状
RPG Maker MV/MZ 游戏读取的存档不是游戏自己的存档文件，导致读档失败、存档不生效。

### 根因分析

RPG Maker MV/MZ 存档在这几个位置，取决于游戏类型：

| 游戏类型 | 存档位置 | 识别方式 |
|---|---|---|
| **MV/MZ (NW.js)** | `游戏目录/www/save/file1.rmmz` | 游戏本身用 NW.js 运行时 |
| **MV (WebView)** | `游戏目录/www/save/file1.rmmz` | 浏览器 localStorage |
| **VX/Ace (RGSS)** | `游戏目录/Save/Save01.rvdata2` | RGD 运行时 |
| **Ren'Py** | `游戏目录/game/saves/` | Ren'Py 引擎 |
| **其他 Steam 游戏** | `drive_c/users/steamuser/AppData/...` | Windows AppData |

当前问题：RPGTL 的存档管理页面（`pages/saves/saves.vue`）可能读的是错的位置。

### 修复方案

#### Step 1：确定 Winlator 容器内游戏存档真实路径

```kotlin
// WineDisplayActivity.kt — 存档路径检测
fun detectSavePath(container: Container, gameExePath: String): String? {
    val driveC = File(container.rootDir, "drive_c")
    
    // 场景 A：游戏在 Wine 的 drive_c 里
    // 例如 /data/.../containers/Game1/drive_c/Program Files/MyGame/
    val gameDir = File(gameExePath).parentFile
    
    // 场景 B：查找 www/save/（RPG Maker MV/MZ）
    val mvSave = listOf(
        File(gameDir, "www/save"),
        File(gameDir, "save"),
        File(driveC, "www/save")
    ).firstOrNull { it.exists() && it.isDirectory }
    if (mvSave != null) return mvSave.absolutePath
    
    // 场景 C：查找 Save/（RPG Maker VX/Ace）
    val vxSave = listOf(
        File(gameDir, "Save"),
        File(driveC, "Save")
    ).firstOrNull { it.exists() && it.isDirectory }
    if (vxSave != null) return vxSave.absolutePath
    
    // 场景 D：查找 game/saves/（Ren'Py）
    val renpySave = listOf(
        File(gameDir, "game/saves"),
        File(driveC, "game/saves")
    ).firstOrNull { it.exists() && it.isDirectory }
    if (renpySave != null) return renpySave.absolutePath
    
    // 场景 E：AppData（Steam 游戏）
    val appData = File(driveC, "users/${container.userName}/AppData")
    if (appData.exists()) {
        // 遍历 AppData 找 .rmmz/.rvdata2 文件
        val saves = appData.walkTopDown()
            .filter { it.extension in setOf("rmmz", "rmmv", "rvdata2", "save") }
            .toList()
        if (saves.isNotEmpty()) return appData.absolutePath
    }
    
    return null
}
```

#### Step 2：把存档路径传给前端

```kotlin
@JavascriptInterface
fun androidGetSavePath(containerId: Int, gamePath: String): String {
    val container = containerManager.getContainerById(containerId) ?: return "{}"
    val savePath = detectSavePath(container, gamePath)
    return JSONObject().apply {
        put("savePath", savePath ?: "")
        put("exists", savePath != null)
        // 列出存档文件
        if (savePath != null) {
            val files = File(savePath).listFiles()?.filter { it.isFile }?.map {
                JSONObject().apply {
                    put("name", it.name)
                    put("size", it.length())
                    put("mtime", it.lastModified())
                }
            }
            put("files", JSONArray(files))
        }
    }.toString()
}
```

#### Step 3：前端存档页读取正确路径

```diff
// pages/saves/saves.vue — 加载存档列表
async function loadSaves() {
-   const saves = await bridge('androidSaves', [category]);
+   // 检查是否有 Wine 容器上下文
+   const containerId = getCurrentContainerId();
+   const gamePath = getCurrentGamePath();
+   
+   if (containerId) {
+       // Wine 模式：从容器读
+       const saveInfo = await bridge('androidGetSavePath', [containerId, gamePath]);
+       if (saveInfo?.savePath) {
+           saves.value = saveInfo.files.map(f => ({
+               slot: f.name,
+               time: formatTime(f.mtime),
+               size: f.size,
+               path: saveInfo.savePath + '/' + f.name
+           }));
+           return;
+       }
+   }
+   // 非 Wine 模式：走原有逻辑
+   const saves = await bridge('androidSaves', [category]);
}
```

#### Step 4：存档编辑也要指向正确路径

存档编辑（修改存档中的金币/物品/角色属性）需要读正确的文件：

```kotlin
@JavascriptInterface
fun androidReadSave(savePath: String): String {
    val file = File(savePath)
    if (!file.exists()) return """{"ok":false,"error":"存档文件不存在"}"""
    
    return try {
        val data = file.readBytes()
        // RPG Maker MV/MZ 存档是 JSON（LZString 压缩）
        val json = LZString.decompressFromUTF16(data.toString(Charsets.UTF_16LE))
        if (json != null) {
            JSONObject().apply {
                put("ok", true)
                put("format", "rmmz_json")
                put("data", JSONObject(json))
            }.toString()
        } else {
            // 未压缩的原始 JSON
            JSONObject().apply {
                put("ok", true)
                put("format", "raw_json")  
                put("data", JSONObject(String(data, Charsets.UTF_8)))
            }.toString()
        }
    } catch (e: Exception) {
        """{"ok":false,"error":"${e.message}"}"""
    }
}
```

---

## P1 优化 1：Wine 注册表性能优化

### 现状
当前 `WineDisplayActivity` 没有对注册表做任何优化。

### 修复

```kotlin
// WineDisplayActivity.kt — 启动前写入性能注册表
private fun optimizeWineRegistry() {
    val rootDir = rootFS!!.rootDir ?: return
    val userReg = File(rootDir, "${RootFS.WINEPREFIX}/user.reg")
    val systemReg = File(rootDir, "${RootFS.WINEPREFIX}/system.reg")
    
    try {
        val editor = WineRegistryEditor(userReg)
        
        // Direct3D 加速
        editor.setDWordValue("Software\\Wine\\Direct3D", "DirectDrawRenderer", 1)  // OpenGL
        editor.setStringValue("Software\\Wine\\Direct3D", "OffscreenRenderingMode", "backbuffer")
        editor.setStringValue("Software\\Wine\\Direct3D", "RenderTargetLockMode", "disabled")
        editor.setStringValue("Software\\Wine\\Direct3D", "UseGLSL", "enabled")
        editor.setStringValue("Software\\Wine\\Direct3D", "StrictDrawOrdering", "disabled")
        editor.setStringValue("Software\\Wine\\Direct3D", "Multisampling", "disabled")
        editor.setDWordValue("Software\\Wine\\Direct3D", "CheckFloatConstants", 0)
        editor.setStringValue("Software\\Wine\\Direct3D", "MaxVersionGL", 0x40005)  // OpenGL 4.5
        
        // 声音缓冲优化
        editor.setDWordValue("Software\\Wine\\Alsa Driver", "OutputBufferSizeMs", 30)
        editor.setDWordValue("Software\\Wine\\Alsa Driver", "PeriodSizeMs", 10)
        
        // 字体缓存加速
        editor.setStringValue("Software\\Wine\\Fonts\\FontSmoothing", "Enabled", "1")
        editor.setDWordValue("Software\\Wine\\Fonts\\FontSmoothing", "Gamma", 1000)
        
        // 输入延迟优化
        editor.setStringValue("Software\\Wine\\X11 Driver", "UseTakeFocus", "N")
        editor.setStringValue("Software\\Wine\\X11 Driver", "InputStyle", "root")
        
        editor.save()
        
        Log.d("PERF", "Wine 注册表优化已应用")
    } catch (e: Exception) {
        Log.w("PERF", "注册表优化失败", e)
    }
}
```

---

## P1 优化 2：CPU 调度 + 进程优先级

### 现状
Wine/Box64 进程和其他 App 用同样的调度优先级，可能被系统限制。

### 修复

```kotlin
// WineDisplayActivity.kt — 进程优先级优化
private fun boostProcessPriority() {
    try {
        // 获取当前进程（Wine 容器）PID
        val myPid = Process.myPid()
        
        // 写入 oom_score_adj 避免被杀
        writeProcFile(myPid, "oom_score_adj", "-1000")
        
        // 设置线程优先级
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_DISPLAY)
        
        // 通过 GuestProgramLauncherComponent 获取 wine 进程 PID
        val winePid = launcherComponent?.currentPid ?: return
        if (winePid > 0 && winePid != myPid) {
            writeProcFile(winePid, "oom_score_adj", "-1000")
            writeProcFile(winePid, "priority", "-10")  // 高优先级
        }
        
        Log.d("PERF", "CPU 优先级优化完成: PID=$myPid, WinePID=$winePid")
    } catch (e: Exception) {
        Log.w("PERF", "CPU 优化跳过（非 root 设备）: ${e.message}")
    }
}

private fun writeProcFile(pid: Int, file: String, value: String) {
    try {
        FileOutputStream("/proc/$pid/$file").use { it.write(value.toByteArray()) }
    } catch (_: Exception) { }
}
```

```diff
// GuestProgramLauncherComponent.java — 暴露 currentPid
+ private int currentPid = -1;
+ public int getCurrentPid() { return currentPid; }
```

---

## P1 优化 3：FPS 显示

### 修复

```kotlin
// WineDisplayActivity.kt — FPS 计数器
class FpsCounter {
    private var frameCount = 0
    private var lastFps = 0
    private var lastTime = System.currentTimeMillis()
    
    fun onFrame() {
        frameCount++
        val now = System.currentTimeMillis()
        if (now - lastTime >= 1000) {
            lastFps = frameCount
            frameCount = 0
            lastTime = now
        }
    }
    
    fun getFps(): Int = lastFps
}
```

```kotlin
// GLSurfaceView 渲染回调中调用
// XServerView 的 GLRenderer.onDrawFrame() 末尾
renderer.setFrameCallback { fpsCounter.onFrame() }
```

```kotlin
// FloatingToolbar.kt — 显示 FPS
private fun updateFpsDisplay() {
    handler.post(object : Runnable {
        override fun run() {
            val fps = fpsCounter.getFps()
            if (fps > 0) {
                findViewById<TextView>(R.id.fpsText)?.text = "${fps} FPS"
                findViewById<TextView>(R.id.fpsText)?.visibility = View.VISIBLE
            }
            handler.postDelayed(this, 1000)
        }
    })
}
```

```vue
<!-- FloatingToolbar 浮动工具栏 — 增加 FPS 显示 -->
<view class="fps-badge">{{ fps }} FPS</view>

<style>
.fps-badge {
  position: absolute; top: 4px; right: 4px;
  background: rgba(0,0,0,0.6); color: #4CAF50;
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
}
</style>
```

---

## 兼容性 1：非 NW.js 游戏的 Agent 回退

### 问题
`RuntimeBridge` 用 CDP（端口 9229）连接 NW.js。但：
- RPG Maker VX/Ace 不使用 NW.js（没有 CDP）
- 非 RPG Maker 游戏（原生 Windows exe）
- 即使 MV 游戏，如果启动参数没传 `--remote-debugging-port`，CDP 也不可用

### 修复

```kotlin
// RuntimeBridge.kt — 多模式 fallback
enum class BridgeMode { CDP, AGENT, NONE }

class RuntimeBridge(private val containerId: String) {
    
    private var mode = BridgeMode.NONE
    
    suspend fun connect(): Boolean {
        // 尝试 CDP（NW.js/Electron）
        if (tryConnectCDP()) {
            mode = BridgeMode.CDP
            return true
        }
        
        // 回退：尝试 TCP Agent（未来）
        if (tryConnectAgent()) {
            mode = BridgeMode.AGENT  
            return true
        }
        
        // 两者都不可用 → 只读文件模式
        mode = BridgeMode.NONE
        return false
    }
    
    private suspend fun tryConnectCDP(): Boolean {
        return tryCDP("http://127.0.0.1:9229/json/list")
    }
    
    private suspend fun tryConnectAgent(): Boolean {
        return trySocket("127.0.0.1", 18567)
    }
    
    // 降级：文件模式读写 RPG Maker 存档
    // 无需 agent，直接修改 Save file
    suspend fun readSaveViaFile(slot: Int): JSONObject? {
        val savePath = detectSavePath(containerId) ?: return null
        val file = File(savePath, "file${slot}.rmmz")
        if (!file.exists()) return null
        // 读取并解析存档 JSON
        val json = LZString.decompressFromUTF16(file.readText())
        return JSONObject(json)
    }
    
    suspend fun writeSaveViaFile(slot: Int, data: JSONObject): Boolean {
        val savePath = detectSavePath(containerId) ?: return false
        val file = File(savePath, "file${slot}.rmmz")
        val compressed = LZString.compressToUTF16(data.toString())
        file.writeText(compressed)
        return true
    }
}
```

---

## 兼容性 2：Ren'Py 支持

### 现状
Ren'Py 游戏基于 Python，不能通过 NW.js CDP 注入。但可以：
1. 通过 Ren'Py 的 RPY 文件直接修改文本
2. 通过 Ren'Py 控制台（按 Shift+O）执行 Python
3. 读取 Ren'Py 存档（.save 文件）

### 修复

```kotlin
// RenPyDetector.kt — 识别 Ren'Py 游戏并处理
class RenPySupport {
    
    fun isRenPyGame(gamePath: String): Boolean {
        val dir = File(gamePath)
        return dir.walkTopDown().any { 
            it.name.equals("renpy.exe", ignoreCase = true) ||
            it.name.equals("renpy.sh", ignoreCase = true) ||
            (it.extension == "rpy" && it.parent?.endsWith("game") == true)
        }
    }
    
    fun extractRenPyTranslations(gamePath: String): List<TranslationEntry> {
        val gameDir = File(gamePath, "game")
        if (!gameDir.exists()) return emptyList()
        
        val entries = mutableListOf<TranslationEntry>()
        
        // 扫描所有 .rpy 文件提取字符串
        gameDir.walkTopDown().filter { it.extension == "rpy" }.forEach { file ->
            val relative = file.relativeTo(gameDir).path
            val lines = file.readLines()
            
            var inTranslateBlock = false
            lines.forEachIndexed { lineNum, line ->
                // Ren'Py 翻译块格式:
                // translate chinese python:
                //     "你好" = "Hello"
                if (line.matches(Regex("\\s*translate\\s+\\w+\\s+"))) {
                    inTranslateBlock = true
                    return@forEachIndexed
                }
                
                if (inTranslateBlock && line.contains("=") && line.contains("\"")) {
                    val parts = line.split("=", limit = 2)
                    val source = parts[1].trim().removeSurrounding("\"")
                    entries.add(TranslationEntry(
                        source = source,
                        target = "",
                        location = "$relative:$lineNum",
                        file = file.name
                    ))
                }
                
                if (line.trim().startsWith("old ") || line.trim().startsWith("new ")) {
                    // Ren'Py 新旧对照翻译格式
                }
            }
        }
        
        return entries
    }
    
    fun injectRenPyTranslation(gamePath: String, 
                                 translations: List<TranslationEntry>): Boolean {
        // 生成或修改 tl/chinese/ 下的翻译文件
        val tlDir = File(gamePath, "game/tl/chinese")
        tlDir.mkdirs()
        
        // 写入 .rpy 翻译文件
        val tlFile = File(tlDir, "android_translation.rpy")
        tlFile.writeText(buildString {
            appendLine("translate chinese python:")
            appendLine()
            translations.forEach { entry ->
                appendLine("    \"${entry.source}\" = \"${entry.target}\"")
            }
        })
        
        return true
    }
}
```

```diff
// WineDisplayActivity.kt — 检测到 Ren'Py 时走不同逻辑
+ if (RenPySupport().isRenPyGame(gameExePath)) {
+     // Ren'Py 不走 CDP
+     // 改为文件级翻译注入
+     Log.d("RENPY", "检测到 Ren'Py 游戏: $gameExePath")
+     // 前端的「汉化」按钮改为文件模式
+ }
```

---

## 前端：游戏条目可设置运行参数

### 问题
当前 Box64 预设、图形驱动、DXVK 版本都硬编码在 Kotlin 里，用户无法调节。

### 修复

```vue
<!-- components/GameLaunchSettings.vue — 新增启动设置弹窗 -->
<template>
  <uni-popup ref="popup" type="center">
    <view class="settings-card">
      <text class="title">{{ game.title }} 启动设置</text>
      
      <view class="field">
        <text>Box64 预设</text>
        <picker :range="box64Presets" range-key="label" @change="onBox64">
          <view class="picker">{{ box64Label }}</view>
        </picker>
      </view>

      <view class="field">
        <text>图形驱动</text>
        <picker :range="graphicsDrivers" range-key="label" @change="onGraphics">
          <view class="picker">{{ graphicsLabel }}</view>
        </picker>
      </view>

      <view class="field">
        <text>DXVK 版本</text>
        <picker :range="dxvkVersions" @change="onDxvk">
          <view class="picker">{{ dxvkLabel }}</view>
        </picker>
      </view>

      <view class="field">
        <text>分辨率</text>
        <picker :range="screenSizes" @change="onScreenSize">
          <view class="picker">{{ screenSizeLabel }}</view>
        </picker>
      </view>

      <view class="field">
        <text>音频驱动</text>
        <picker :range="audioDrivers" range-key="label" @change="onAudio">
          <view class="picker">{{ audioLabel }}</view>
        </picker>
      </view>

      <button class="button primary" @tap="saveAndLaunch">保存并启动</button>
      <button class="button secondary" @tap="close">取消</button>
    </view>
  </uni-popup>
</template>

<script setup>
const BOX64_PRESETS = [
  { value: 'performance', label: '⚡ 性能优先' },
  { value: 'stability',   label: '🛡️ 稳定优先' },
  { value: 'conservative', label: '🐢 保守兼容' },
  { value: 'intermediate', label: '⚖️ 中等' },
  { value: 'wine',         label: '🍷 仅 Wine' },
]
const GRAPHICS_DRIVERS = [
  { value: 'turnip',     label: 'Turnip Vulkan (高通推荐)' },
  { value: 'virgl',      label: 'VirGL OpenGL (Mali推荐)' },
  { value: 'system_vulkan', label: '系统 Vulkan' },
  { value: 'wined3d',    label: 'WineD3D (最兼容)' },
]
const DXVK_VERSIONS = ['dxvk-2.6.1', 'dxvk-2.5.2', 'dxvk-2.3.1', 'dxvk-2.2']
const SCREEN_SIZES = ['1280x720', '1366x768', '1920x1080', '854x480']
const AUDIO_DRIVERS = [
  { value: 'alsa', label: 'ALSA (低延迟)' },
  { value: 'pulseaudio', label: 'PulseAudio (兼容)' },
]

async function saveAndLaunch() {
  // 保存配置到 localStorage（按游戏路径索引）
  const configs = JSON.parse(uni.getStorageSync('game_launch_configs') || '{}')
  configs[game.path] = {
    box64Preset: selectedBox64,
    graphicsDriver: selectedGraphics,
    dxvkVersion: selectedDxvk,
    screenSize: selectedScreenSize,
    audioDriver: selectedAudio,
  }
  uni.setStorageSync('game_launch_configs', JSON.stringify(configs))
  
  // 启动游戏
  bridge('androidLaunchGame', [game.path, game.title, game.backend, selectedBox64])
}
</script>
```

```diff
// 游戏库游戏条目组件（GameCard.vue）增加「⚙️ 设置」按钮
+ <button class="icon-btn" @tap.stop="showSettings">
+   ⚙️
+ </button>
```

---

## 存档：Wine 容器存档与 RPGTL 存档管理双向同步

### 问题
RPGTL 的存档管理页面只能管理非 Wine 模式下的存档。Wine 容器内游戏的存档存在容器路径里，两个管理界面不通。

### 修复

```kotlin
// SaveSyncBridge.kt — 存档同步桥
class SaveSyncBridge(private val context: Context) {
    
    /**
     * 把 Wine 容器存档复制到 RPGTL 可见位置
     */
    fun syncFromContainer(containerId: Int, savePath: String, targetDir: String): Int {
        val saveDir = File(savePath)
        if (!saveDir.exists()) return 0
        
        var count = 0
        val target = File(targetDir, "wine_$containerId")
        target.mkdirs()
        
        saveDir.listFiles()?.forEach { file ->
            if (file.isFile && file.extension in SAVE_EXTENSIONS) {
                file.copyTo(File(target, file.name), overwrite = true)
                count++
            }
        }
        return count
    }
    
    /**
     * 把 RPGTL 修改后的存档写回 Wine 容器
     */
    fun syncToContainer(containerId: Int, targetDir: String, savePath: String): Int {
        val source = File(targetDir, "wine_$containerId")
        if (!source.exists()) return 0
        
        val saveDir = File(savePath)
        if (!saveDir.exists()) saveDir.mkdirs()
        
        var count = 0
        source.listFiles()?.forEach { file ->
            if (file.isFile && file.extension in SAVE_EXTENSIONS) {
                file.copyTo(File(saveDir, file.name), overwrite = true)
                count++
            }
        }
        return count
    }
    
    /**
     * 获取容器存档列表（给前端存档页）
     */
    fun listContainerSaves(containerId: Int, savePath: String): JSONArray {
        val saveDir = File(savePath)
        if (!saveDir.exists()) return JSONArray()
        
        val saves = JSONArray()
        saveDir.listFiles()?.filter { it.isFile && it.extension in SAVE_EXTENSIONS }
            ?.sortedByDescending { it.lastModified() }
            ?.forEach { file ->
                saves.put(JSONObject().apply {
                    put("name", file.name)
                    put("size", file.length())
                    put("mtime", file.lastModified())
                    put("slot", extractSlotNumber(file.name))
                })
            }
        return saves
    }
    
    companion object {
        val SAVE_EXTENSIONS = setOf("rmmz", "rmmv", "rvdata2", "save", "lsd")
    }
}
```

```kotlin
// 前端 bridge
@JavascriptInterface
fun androidListContainerSaves(containerId: Int, savePath: String): String {
    val sync = SaveSyncBridge(this)
    return sync.listContainerSaves(containerId, savePath).toString()
}

@JavascriptInterface
fun androidSyncSaves(containerId: Int, savePath: String, direction: String): String {
    val sync = SaveSyncBridge(this)
    val targetDir = File(filesDir, "saves").absolutePath
    
    val count = if (direction == "from_container") {
        sync.syncFromContainer(containerId, savePath, targetDir)
    } else {
        sync.syncToContainer(containerId, targetDir, savePath)
    }
    
    return """{"ok":true,"count":$count}"""
}
```

```diff
// pages/saves/saves.vue — 存档页检测 Wine 容器
async function loadSaves() {
+   const containerId = getCurrentContainerId()
+   const savePath = await bridge('androidGetSavePath', [containerId, gamePath])
+   
+   if (savePath?.savePath) {
+       // Wine 容器存档
+       const saves = await bridge('androidListContainerSaves', [containerId, savePath.savePath])
+       savesList.value = JSON.parse(saves)
+   } else {
+       // 原来的逻辑
+   }
}
```

```vue
<!-- pages/saves/saves.vue — 存档页新增同步按钮 -->
<view class="toolbar" v-if="isWineMode">
  <button class="button" @tap="syncSaves('from_container')">
    📥 从容器同步到工具
  </button>
  <button class="button" @tap="syncSaves('to_container')">
    📤 写回容器
  </button>
</view>
```

---

## 实现优先级

| 优先级 | 任务 | 工作量 |
|---|---|---|
| 🔴 **致命** | 存档位置指向错误 | 半天 |
| 🟡 P1 | Wine 注册表优化 | 1h |
| 🟡 P1 | CPU 调度优化 | 1h |
| 🟡 P1 | FPS 显示 | 30min |
| 🟢 P2 | Ren'Py 识别 + 文本提取 | 2h |
| 🟢 P2 | 游戏启动设置弹窗 | 半天 |
| 🟢 P2 | 存档双向同步 | 1h |
| 🔵 P3 | TCP Agent fallback | 2h |

**建议先修存档 Bug（致命），再做 P1 性能，剩下 P2 慢慢搞。**

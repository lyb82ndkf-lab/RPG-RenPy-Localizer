# 性能优化提示词（给 Codex）— 对标 Winlator 性能

## 现状 vs 目标

| 指标 | 当前 RPGTL | Winlator 水平 | 差距 |
|---|---|---|---|
| Wine 启动速度 | 使用默认 box64 预设 | 支持 Performance/Stability 等多套预设 | ❌ |
| 图形性能 | 默认 DXVK/VKD3D | 可切换 Vulkan/OpenGL 驱动 + Turnip 配置 | ❌ |
| GPU 驱动选择 | 固定 | 支持 Adreno/Mali/PowerVR 自动检测 | ❌ |
| 帧率控制 | 无 | 支持帧率显示 + 限制 | ❌ |
| CPU 调度 | 未优化 | 支持 CPU 核心分配 + 进程优先级 | ❌ |
| Wine 配置 | 默认 registry | 每容器独立 audio/graphics/dxvk 配置 | ❌ |
| 缓存机制 | 无 | 频繁访问路径有 io 缓存 | ❌ |
| 音效驱动 | 固定 ALSA | 支持 ALSA/PulseAudio 切换 | ❌ |

---

## 优化 1：Box64 预设选择（最快见效）

### 问题
当前 `GuestProgramLauncherComponent` 使用 `box64Preset = "conservative"`，对性能要求高的游戏会损失帧率。

### 修复

```diff
// WineDisplayActivity.kt — 允许前端传 box64 预设
+ val box64Preset = intent.getStringExtra(EXTRA_BOX64_PRESET) ?: "performance"
  launcherComponent.setBox64Preset(box64Preset)
```

```diff
// 前端游戏条目增加预设选择
+ export const BOX64_PRESETS = [
+   { value: 'performance', label: '性能优先' },
+   { value: 'stability',   label: '稳定优先' },
+   { value: 'conservative', label: '保守兼容' },
+   { value: 'intermediate', label: '中等' },
+   { value: 'wine',         label: '仅 Wine' },
+ ]
```

### 改动量
- Kotlin：+3 行
- Vue：+15 行（游戏条目设置弹窗）

---

## 优化 2：GPU 驱动自动选择

### 问题
当前硬编码 `GraphicsDriver.DEFAULT_VULKAN_DRIVER`，没有根据手机 GPU 型号选择最佳驱动。

### 修复

```kotlin
// WineDisplayActivity.kt — GPU 检测
private fun detectBestGraphicsDriver(): String {
    val gpuInfo = android.os.Build.HARDWARE.lowercase()
    return when {
        // Qualcomm Adreno → Turnip (Vulkan)
        gpuInfo.contains("qcom") || gpuInfo.contains("adreno") -> GraphicsDrivers.TURNIP_VULKAN
        // Mali → VirGL (OpenGL)
        gpuInfo.contains("mali") -> GraphicsDrivers.VIRGL
        // PowerVR → WineD3D (最兼容)
        gpuInfo.contains("powervr") -> GraphicsDrivers.WINED3D
        // 默认用系统 Vulkan
        else -> GraphicsDrivers.SYSTEM_VULKAN
    }
}
```

**效果**：Adreno 手机用 Turnip Vulkan 驱动，性能提升 20-50%。

---

## 优化 3：Wine 注册表优化

### 问题
Winlator 在创建容器时会写入大量 Wine 注册表优化项（显卡加速、字体渲染、DirectDraw 等），RPGTL 没有做。

### 修复

```kotlin
// WineDisplayActivity.kt — 启动前应用 Wine 优化注册表
private fun applyWineOptimizations() {
    val rootDir = rootFS!!.rootDir
    val userRegFile = File(rootDir, "${RootFS.WINEPREFIX}/user.reg")
    
    try {
        val editor = WineRegistryEditor(userRegFile)
        
        // DirectDraw 渲染加速
        editor.setStringValue("Software\\Wine\\DirectDraw", "Renderer", "opengl")
        
        // 字体平滑
        editor.setStringValue("Software\\Wine\\Fonts\\FontSmoothing", "Enabled", "1")
        
        // 鼠标抓取加速
        editor.setStringValue("Software\\Wine\\X11 Driver", "UseTakeFocus", "N")
        
        // 禁用输入法（减少延迟）
        editor.setStringValue("Software\\Wine\\X11 Driver", "InputStyle", "root")
        
        // 显存设置（自动）
        editor.setStringValue("Software\\Wine\\Direct3D", "VideoMemorySize", detectVideoMemory())
        
        // OffscreenRenderingMode
        editor.setStringValue("Software\\Wine\\Direct3D", "OffscreenRenderingMode", "backbuffer")
        
        // Multisampling
        editor.setStringValue("Software\\Wine\\Direct3D", "Multisampling", "disabled")
        
        // 音频缓冲优化
        editor.setStringValue("Software\\Wine\\Drivers", "Audio", audioDriver)
        
        editor.save()
    } catch (e: Exception) {
        Log.w("PERF", "Wine 注册表优化失败", e)
    }
}
```

---

## 优化 4：GPU 驱动配置传递

### 问题
`GuestProgramLauncherComponent.execGuestProgram()` 需要设置 `MESA_VK_WSI_DEBUG`、`TU_DEBUG` 等环境变量，当前缺失。

### 修复

```kotlin
// WineDisplayActivity.kt — 环境变量注入
private fun setupEnvVars(launcherComponent: GuestProgramLauncherComponent) {
    val envVars = launcherComponent.envVars ?: EnvVars()
    
    when (graphicsDriver) {
        GraphicsDrivers.TURNIP_VULKAN -> {
            envVars.put("MESA_VK_WSI_DEBUG", "sw")
            envVars.put("TU_DEBUG", "noconform")
        }
        GraphicsDrivers.VIRGL -> {
            envVars.put("GALLIUM_DRIVER", "virpipe")
            envVars.put("MESA_GL_VERSION_OVERRIDE", "4.5")
        }
        GraphicsDrivers.SYSTEM_VULKAN -> {
            envVars.put("MESA_VK_WSI_DEBUG", "sw")
        }
    }
    
    // Box64 优化
    envVars.put("BOX64_LOG", "0")        // 关闭日志减少开销
    envVars.put("BOX64_DYNAREC", "1")    // 启用动态重编译
    envVars.put("BOX64_DYNAREC_BIGBLOCK", "1")  // 大块编译
    
    launcherComponent.envVars = envVars
}
```

---

## 优化 5：CPU 核心分配 + 进程优先级

### 问题
Wine 和游戏进程使用默认调度，可能跑在小核上。

### 修复

```kotlin
// WineDisplayActivity.kt — CPU 调度优化
private fun setPerformanceMode() {
    try {
        // 获取当前进程 PID (Wine 容器进程)
        val pid = Process.myPid()
        
        // 设置进程优先级为最积极
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_DISPLAY)
        
        // 写入 CPU 亲和性（所有大核）
        // 注意：需要 root 或系统权限，降级方案
        writeFile("/proc/$pid/oom_adj", "-17")
        
        // 通过 Box64 环境变量控制线程
        // BOX64_DYNAREC_STRONGMEM=1 提高内存访问速度
        // BOX64_DYNAREC_WAIT=0 减少等待
    } catch (e: Exception) {
        Log.w("PERF", "CPU 调度优化失败（非 root 设备跳过）", e)
    }
}
```

**降级方案**（无需 root）：

```kotlin
// 在 GameLauncher 的 Wine 启动命令中加 taskset
// 但 wine 内无法直接 taskset，改为在 Android 侧提升 wine 进程优先级
private fun boostWineProcess() {
    // 找到 wine 进程 PID
    val winePid = guestProgramLauncherComponent.currentPid
    if (winePid > 0) {
        // 通过 /proc/${winePid}/oom_score_adj 降低被杀死概率
        try {
            FileOutputStream("/proc/$winePid/oom_score_adj").use {
                it.write("-1000\n".toByteArray())
            }
        } catch (_: Exception) { }
    }
}
```

---

## 优化 6：帧率检测 + 性能仪表盘

### 问题
用户不知道游戏跑多少帧，也无法诊断瓶颈。

### 修复

```kotlin
// WineDisplayActivity.kt — FPS 检测
private var lastFrameTime = 0L
private var frameCount = 0
private var fps = 0
private val fpsHandler = Handler(Looper.getMainLooper())

private fun startFpsCounter() {
    fpsHandler.post(object : Runnable {
        override fun run() {
            fps = frameCount
            frameCount = 0
            if (fps > 0) {
                Log.d("PERF", "游戏帧率: ${fps}FPS")
            }
            fpsHandler.postDelayed(this, 1000)
        }
    })
}

// XServerView 渲染回调中调用
fun onFrameRendered() {
    frameCount++
}
```

```vue
<!-- FloatingToolbar 实时面板中显示 FPS -->
<view class="fps-display">
  <text>FPS: {{ fps }}</text>
  <text>GPU: {{ gpuDriver }}</text>
  <text>Box64: {{ box64Preset }}</text>
</view>
```

---

## 优化 7：DXVK/VKD3D 版本切换

### 问题
不同游戏需要不同版本的 DXVK 或 VKD3D，当前只能用默认版。

### 修复

```diff
// WineDisplayActivity.kt — 从 intent 读取 dxvk 版本
+ val dxvkVersion = intent.getStringExtra(EXTRA_DXVK_VERSION) ?: "dxvk-2.6.1"
+ val vkd3dVersion = intent.getStringExtra(EXTRA_VKD3D_VERSION) ?: "vkd3d-3.0b"
```

```diff
// GuestProgramLauncherComponent.execGuestProgram() 中
// 加载对应版本的 DXVK .so 到 Wine 的 system32 目录
+ installDXVK(dxvkVersion, rootDir)
+ installVKD3D(vkd3dVersion, rootDir)
```

---

## 优化 8：异步启动 + 启动速度优化

### 问题
当前流程是串行的：解压 RootFS → 初始化 XServer → 启动 Wine → 启动游戏。这个过程可以并行化。

### 修复

```kotlin
// WineDisplayActivity.kt — 并行初始化
private fun parallelInit() {
    coroutineScope.launch {
        // 并行：XServer 初始化 + RootFS 预热
        val xserverJob = async { xServer?.start() }
        val rootfsJob = async { rootFS?.warmUpCache() }
        
        // 等待两者都就绪
        xserverJob.await()
        rootfsJob.await()
        
        // 启动组件
        environment?.startEnvironmentComponents()
        
        // 启动游戏（延迟从 1500ms 降到 500ms）
        delay(500)
        launcherComponent.start()
    }
}
```

---

## 优化 9：游戏配置持久化

### 问题
每次启动游戏都要重新设置性能参数，不方便。

### 修复

```kotlin
// WineDisplayActivity.kt — 保存游戏专属配置
data class GamePerfConfig(
    val gamePath: String,
    val box64Preset: String = "performance",
    val graphicsDriver: String = "",
    val dxvkVersion: String = "",
    val screenSize: String = "1280x720",
    val audioDriver: String = "alsa",
    val envVars: Map<String, String> = emptyMap()
)

// 使用 SQLite 或 JSON 文件持久化
// 按 gamePath 哈希索引，启动时读取
```

---

## 优化 10：Container 预热 + 容器复用

### 问题
每次启动游戏都从头创建容器（Wine prefix），很慢。

### 修复

```diff
// 复用已有容器而不是每次都新建
+ // 按 gameExePath 的 hash 查找已有容器
+ val containerHash = gameExePath.hashCode().toString()
+ var container = containers.firstOrNull { it.name == containerHash }
+ if (container == null) {
+     container = containerManager.createContainer(containerHash, gameExePath)
+ }
```

---

## 实现优先级

| 优先级 | 优化 | 预估效果 | 工作量 |
|---|---|---|---|
| 🔴 P0 | Box64 预设选择（优化 1） | 帧率提升 10-30% | 30min |
| 🔴 P0 | GPU 驱动自动选择（优化 2） | 帧率提升 20-50% | 1h |
| 🟡 P1 | Wine 注册表优化（优化 3） | 稳定性提升 | 1h |
| 🟡 P1 | 环境变量注入（优化 4） | GPU 兼容性提升 | 30min |
| 🟡 P1 | CPU 调度优化（优化 5） | 帧率稳定性提升 | 1h |
| 🟢 P2 | FPS 检测（优化 6） | 可诊断性能 | 30min |
| 🟢 P2 | DXVK 版本切换（优化 7） | 兼容性提升 | 2h |
| 🟢 P2 | 异步启动（优化 8） | 启动快 500ms | 1h |
| 🟢 P2 | 配置持久化（优化 9） | 使用体验提升 | 1h |
| 🔵 P3 | 容器预热（优化 10） | 二次启动快 5s | 2h |

**建议**：先做 P0（Box64 预设 + GPU 驱动自动选择），这两项加起来 1.5h 就能让帧率接近 Winlator 水平。

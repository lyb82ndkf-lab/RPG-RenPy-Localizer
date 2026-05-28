# Bug 修复提示词（v4 — 代码审查发现的遗留 Bug）

---

## 🔴 Bug 1（高危）：AppUtils.INTERNAL_STORAGE 包名硬编码

### 根因

Winlator 引擎代码迁移时，`AppUtils.java` 中的 `INTERNAL_STORAGE` 常量**未更新包名**：

```java
// AppUtils.java 第 47 行 — 仍用 Winlator 的包名！
public static final String INTERNAL_STORAGE = "/data/data/com.winlator/storage";
```

当前项目包名是 `com.rpgrtl`，这个路径指向 `com.winlator` 的目录，**永远不存在**。任何使用这个常量的功能都会静默失败——Wine 引擎的容器存储、RootFS 缓存、配置文件全部写到错误路径，但因为没有显式崩溃，用户根本感知不到。

### 影响范围

`INTERNAL_STORAGE` 被引用的位置：

1. **RootFS.java** — Wine 前缀路径拼接
2. **Container.java** — 容器目录创建
3. **WineUtils.java** — Wine 版本管理
4. **WineStartMenuCreator.java** — 快捷方式创建
5. **SettingsFragment.java** — 设置持久化

所有 Wine 引擎相关功能都在这个错误路径上操作。

### 修复

```diff
// AppUtils.java — 一行修复
- public static final String INTERNAL_STORAGE = "/data/data/com.winlator/storage";
+ public static final String INTERNAL_STORAGE = "/data/data/com.rpgrtl/storage";
```

**但更好的做法**：不要硬编码路径，用 `context.getFilesDir()` 动态获取：

```java
// 改用动态方法而非静态常量
public static String getInternalStorage(Context context) {
    return context.getFilesDir() + "/storage";
}
```

```diff
// AppUtils.java — 新增方法
+ public static String getInternalStorage(Context context) {
+     return context.getFilesDir().getAbsolutePath() + "/storage";
+ }
```

```diff
// 所有引用处替换：
- String path = AppUtils.INTERNAL_STORAGE + "/containers";
+ String path = AppUtils.getInternalStorage(context) + "/containers";
```

---

## 🔴 Bug 2（高危）：WineDisplayActivity 物理返回键不停止游戏

### 根因

`WineDisplayActivity.kt` 没有重写 `onBackPressed()` 或 `onKeyDown()`。用户按物理返回键时，Activity 直接 `finish()`，但 **不会**：
- 发送 stop 命令给 GameLauncherComponent（Wine 进程继续跑）
- 关闭 CDP WebSocket 连接（RuntimeBridge 泄漏）
- 清理 Wine 容器进程和共享内存

后果：每次按返回键退出游戏，后台积一个残缺的 Wine 进程，内存泄漏，再启动新游戏时端口抢占。

### 修复

```kotlin
// WineDisplayActivity.kt — 新增 onBackPressed 处理
override fun onBackPressed() {
    // 弹出确认对话框，防止误操作
    AlertDialog.Builder(this)
        .setTitle("退出游戏")
        .setMessage("是否退出当前游戏？")
        .setPositiveButton("退出") { _, _ ->
            stopGame()  // 必须先停引擎再 finish
            finish()
        }
        .setNegativeButton("继续游戏", null)
        .show()
}

override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
    if (keyCode == KeyEvent.KEYCODE_BACK) {
        onBackPressed()
        return true
    }
    return super.onKeyDown(keyCode, event)
}
```

```kotlin
// 完善 stopGame() 方法
private fun stopGame() {
    // 1. 停止 RuntimeBridge（关闭 CDP/Agent 连接）
    runtimeBridge?.disconnect()
    
    // 2. 停止 GuestProgramLauncherComponent（杀掉 Wine 进程）
    launcherComponent?.stop()
    
    // 3. 停止 XEnvironment
    try { environment?.stopEnvironmentComponents() } catch (_: Exception) {}
    
    // 4. 暂停 XServerView 渲染
    try { xServerView?.onPause() } catch (_: Exception) {}
    
    // 5. 释放共享内存
    try { sysVShmComponent?.release() } catch (_: Exception) {}
    
    Log.d("WINE", "游戏已停止，所有资源已释放")
}
```

---

## 🟡 Bug 3（中危）：WineSaveService 不匹配 Slot*.save 格式

### 根因

```kotlin
// WineSaveService.kt 第 25 行
private val SAVE_FILE_REGEX = Regex("""(?:file|save)?(\d+).*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd)""", ...)
```

这个正则不匹配 `Slot1.save` 或 `Slot01.save` 格式。部分 RPG Maker 修改版或加密版会使用 `Slot` 前缀。

### 修复

```diff
- Regex("""(?:file|save)?(\d+).*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd)""")
+ Regex("""(?:file|save|slot|autosave)?(\d+).*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd|sav)""", RegexOption.IGNORE_CASE)
```

同样更新非 Wine 模式的 `AndroidRpgMakerService.kt`：

```diff
- private val SAVE_FILE_REGEX = Regex("""(?:file|save)?(\d+).*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd)""", ...)
+ private val SAVE_FILE_REGEX = Regex("""(?:file|save|slot|autosave)?(\d+).*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd|sav)""", RegexOption.IGNORE_CASE)
```

---

## 🟡 Bug 4（中危）：coerceValue() 输入验证缺失

### 根因

```kotlin
// AndroidRpgMakerService.kt 第 640-642 行
private fun coerceValue(text: String, old: Any?): Any {
    return when (old) {
        is Int -> text.toInt()       // ← abc → NumberFormatException
        is Double -> text.toDouble() // ← 同上
        is Long -> text.toLong()     // ← 同上
        is Boolean -> text.equals("true", ignoreCase = true)
        else -> text
    }
}
```

用户输入非数字时抛异常，虽然被外层 catch 捕获只返回 `{ok:false}`，但用户不知道具体原因。

### 修复

```diff
- is Int -> text.toInt()
- is Double -> text.toDouble()
- is Long -> text.toLong()
+ is Int -> text.toIntOrNull() ?: old  // 转换失败时保留旧值
+ is Double -> text.toDoubleOrNull() ?: old
+ is Long -> text.toLongOrNull() ?: old
```

同时在 `updateRecord()` 中增加提示：

```kotlin
val coerced = coerceValue(text, old)
if (old is Number && coerced == old && !text.matches(Regex("-?\\d*\\.?\\d+"))) {
    return JSONObject().apply {
        put("ok", false)
        put("error", "输入 '${text}' 不是有效数字，已保留旧值")
    }
}
```

---

## 🟡 Bug 5（中危）：maps() 的地图 ID fallback 逻辑错误

### 根因

```kotlin
// AndroidRpgMakerService.kt 第 108 行
for (index in 0 until mapInfos.length()) {
    val item = mapInfos.optJSONObject(index) ?: continue
    val id = item.optInt("id", index)  // ← 当 id=null 时 fallback 到 index
    val name = item.optString("name", "Map ${index+1}")
    maps.put(JSONObject().apply {
        put("id", id)
        put("name", name)
    })
}
```

RPG Maker 的 `MapInfos.json` 格式是 `{"1": {...}, "2": {...}, ...}`，其中 key 才是真正的 id。`MapInfos.json` 以数组形式存储，每个元素的 `id` 字段就是 key 值，不会有 `null` 的情况。但万一遇到损坏的 MapInfos，fallback 到数组索引会导致 id 错位。

### 修复

```diff
for (index in 0 until mapInfos.length()) {
    val item = mapInfos.optJSONObject(index) ?: continue
+   val id = item.optInt("id", -1)
+   val realId = if (id >= 0) id else index + 1  // fallback: index+1 而非 index
    val name = item.optString("name", "地图 ${index+1}")
    maps.put(JSONObject().apply {
-       put("id", id)
+       put("id", realId)
        put("name", name)
    })
}
```

---

## 🟢 Bug 6（低优）：备份未使用用户期望的 mtool/ 目录

用户期望存档备份到 `mtool/` 目录（与桌面版 MTool 工具一致），但当前备份路径是 `.rpgrtl_android/backup/save/`。

### 修复

```diff
// AndroidRpgMakerService.kt — createSaveBackup()
- val backupDir = File(dataDir.root.parentFile, ".rpgrtl_android/backup/save")
+ // 优先存到 mtool/ 目录（与桌面版工具兼容）
+ val mtoolDir = File(dataDir.root.parentFile, "mtool/backup/save")
+ val backupDir = if (mtoolDir.canWrite()) mtoolDir
+     else File(dataDir.root.parentFile, ".rpgrtl_android/backup/save")
```

---

## 修复优先级

| 优先级 | Bug | 影响 | 改动量 |
|---|---|---|---|
| 🔴 **P0** | `INTERNAL_STORAGE` 包名错误 | Wine 引擎全部功能静默失败 | 改 1 个常量 |
| 🔴 **P0** | 物理返回键不清理进程 | 后台 Wine 进程泄漏，内存暴涨 | Kotlin +20 行 |
| 🟡 P1 | Wine 存档 regex 缺 Slot 格式 | 部分存档无法读取 | 改 1 行正则 |
| 🟡 P1 | coerceValue 输入验证 | 数字输入错误时提示不友好 | Kotlin +5 行 |
| 🟡 P1 | maps() id 回退 | 罕见情况下地图白屏 | Kotlin +3 行 |
| 🟢 P2 | 备份未用 mtool 目录 | 不致命 | Kotlin +10 行 |

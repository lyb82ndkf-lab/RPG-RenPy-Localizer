# Bug 修复提示词（v3 — 根本原因驱动）

---

## Bug 1：左侧对象列表只能显示 30 条

### 根因（已追溯）

```
前端 api/data.ts → bridge('androidDataRecords', [category, limit])
  → Kotlin ShellBridge.kt: androidDataRecords(category, limit) 
    → AndroidRpgMakerService.kt: dataRecords(category, limit)
      → listRecords(data, limit) → addRecord() 检查 if (out.length() >= limit) return
```

问题出在**多层调用中某处 `limit` 参数丢失**：

- `store/data.ts:load()` 调用 `api.dataRecords(category.value, 5000)` — 已传 5000 ✅
- `api/data.ts:dataRecords()` 调用 `bridge('androidDataRecords', [category, limit])` — 传了数组两个元素 ✅
- 但 **ShellBridge.kt 收到 `limit=0`**，因为 Kotlin 的 `@JavascriptInterface` 方法不能直接从 JSON 数组参数解析

**关键**：UniApp 的 `uni.webView.navigateTo` 或 `shellJson()` 在序列化参数时，如果第二个参数 `limit` 是 `null` 或 `undefined`，JS 侧会跳过不传，Kotlin 侧 `Int` 参数收到 `0`，然后 `coerceIn(1,5000)` 变 `1`。

### 修复

```typescript
// store/data.ts — 强制 limit 有值
async function load(category: string) {
  const data = await bridge('androidDataRecords', category, 5000)
  // 或者传对象而非数组
  // const data = await bridge('androidDataRecords', JSON.stringify({ category, limit: 5000 }))
}
```

```typescript
// api/data.ts — 确保 limit 有默认值
export function dataRecords(category: string, limit = 5000) {
  if (isAndroidShell()) {
    return shellJson('androidDataRecords', JSON.stringify({
      category, limit
    }))
  }
  // ...
}
```

```kotlin
// ShellBridge.kt 或 MainActivity.kt — 改为 JSON 对象接收
@JavascriptInterface
fun androidDataRecords(json: String): String {
    val request = JSONObject(json)
    val category = request.optString("category", "")
    val limit = request.optInt("limit", 5000)
    // ...
}
```

**或者更简单的修法**：在 `AndroidRpgMakerService.kt` 里把默认 limit 改为 `Int.MAX_VALUE` 而不是依靠前端传值：

```kotlin
// AndroidRpgMakerService.kt — dataRecords 方法
fun dataRecords(category: String, limit: Int = Int.MAX_VALUE): String {
    // limit 不再 coerceIn 到 5000，而是保留传入值
    val effectiveLimit = if (limit <= 0) Int.MAX_VALUE else limit
    // ...
}
```

---

## Bug 2：存档不读游戏自己的存档

### 根因（已追溯）

```
AndroidRpgMakerService.kt 第 726 行：

private val SAVE_FILE_REGEX = Regex("""file(\d+)\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd)""", ...)
```

RPG Maker MV 默认存档格式：`Save1.rmmzsave`（以 "Save" 开头，不是 "file"）
正则只匹配 `file1.rmmzsave`（以 "file" 开头），所以 `saveSlots()` 扫描目录时找不到任何存档。

对比 **WineSaveService.kt 第 157 行**（Wine 模式下正常工作）：

```kotlin
private val SAVE_FILE_REGEX = Regex("""(?:file|save)?(\d+).*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd)""", ...)
```

Wine 模式的 regex 正确匹配了 `Save1.rmmzsave`。

### 修复

```diff
// AndroidRpgMakerService.kt — 一行修复
- private val SAVE_FILE_REGEX = Regex("""file(\d+)\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd)""", RegexOption.IGNORE_CASE)
+ // 匹配 file1.rmmzsave 或 Save1.rmmzsave 或 Save01.rmmzsave
+ private val SAVE_FILE_REGEX = Regex("""(?:file|save)?(\d+).*\.(rpgsave|rmmzsave|rmmz|rmmv|rvdata2|save|lsd)""", RegexOption.IGNORE_CASE)
```

```kotlin
// 同时修复 saveSlots() 中的额外过滤逻辑
// 如果有 additionalFilter，确保也支持 Save 前缀的文件
fun saveSlots(): JSONObject {
    val slotList = JSONArray()
    for (dir in findSaveDirs()) {
        val files = dir.listFiles()
        files?.forEach { file ->
            val match = SAVE_FILE_REGEX.find(file.name)
            if (match != null) {
                val slotNumber = match.groupValues[1].toIntOrNull() ?: return@forEach
                slotList.put(JSONObject().apply {
                    put("slot", slotNumber)
                    put("file", file.name)
                    put("uri", file.uri.toString())
                    put("mtime", file.lastModified())
                    put("size", file.length())
                })
            }
        }
    }
    return JSONObject().apply {
        put("slots", slotList)
        put("count", slotList.length())
    }
}
```

---

## Bug 3：键盘弹出界面缩放变大

### 根因（已追溯）

```
AndroidAPP/AndroidAPP/index.html 第 11 行：

<meta name="viewport" content="width=device-width, user-scalable=no,
  initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0,
  interactive-widget=resizes-content" />
```

`interactive-widget=resizes-content` 在键盘弹出时，让可视区域（viewport）**缩小**到键盘上方的剩余空间。所有 CSS 相对单位（`vw`/`vh`/`rpx`）基于新视口重新计算，页面元素被压缩到更小的空间内，视觉上就「缩放变大了」。

`resizes-content` 是标准的 CSS 行为，但在 UniApp H5 + Android WebView 的组合下，配合 `user-scalable=no` + `max/min-scale=1.0` 会产生冲突：WebView 想重排内容，但被 scale 锁定阻止，于是用「放大焦点元素」来妥协。

### 修复

```diff
// index.html — 改 interactive-widget 策略
- <meta name="viewport" content="width=device-width, user-scalable=no,
-   initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0,
-   interactive-widget=resizes-content" />
+ <meta name="viewport" content="width=device-width, user-scalable=no,
+   initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0" />
+ <!-- 完全移除 interactive-widget 属性，让 WebView 使用默认行为 -->
```

```javascript
// App.vue 或 main.js — 键盘弹出时固定窗口高度
let originalViewportHeight = 0;

// #ifdef H5
window.addEventListener('resize', function() {
  const keyboardVisible = window.innerHeight < window.outerHeight * 0.8;
  if (keyboardVisible) {
    // 键盘弹出：固定视口高度
    if (originalViewportHeight === 0) {
      originalViewportHeight = window.innerHeight;
    }
    document.documentElement.style.height = originalViewportHeight + 'px';
    document.body.style.height = originalViewportHeight + 'px';
    document.body.style.overflow = 'hidden';
  } else {
    // 键盘收起：恢复正常
    document.documentElement.style.height = '';
    document.body.style.height = '';
    document.body.style.overflow = '';
    originalViewportHeight = 0;
  }
});
// #endif
```

```scss
// uni.scss — 确保输入框没有 transform scale
.input {
  // 移除 transform: scale(...) — 如果存在的话
  // transform: scale(0.82);  ← 删掉这行
  // transform-origin: left center;  ← 删掉这行
  font-size: 16px;  // 直接设字号而非 scale
}
```

---

## Bug 4：汉化界面无法正常翻译

### 根因（已追溯）

调用链：
```
translate.vue: runAi()
  → store/translation.ts: translateVisible(settings)
    → api/translate.ts: aiTranslate(settings, chunk)
      → bridge('androidAiTranslate', JSON.stringify({settings, entries}))
        → AndroidAiTranslationService.kt: translate(settings, entries)
          → HTTP POST → AI API (DeepSeek/OpenAI etc.)
          → 解析响应 → 返回 { translations: [...] }
```

翻译不生效的几种可能及其验证方式：

**可能 A：API Key 为空或无效**
```kotlin
// AndroidAiTranslationService.kt 第 28 行
if (apiKey.isBlank()) {
    return JSONObject().put("error", "API Key 未设置")
}
```
→ 验证：打开 AI 设置，确认 API Key 已填写

**可能 B：网络不通（国内无法直接访问 DeepSeek API）**
→ 验证：在 AI 设置页点「测试连接」按钮

**可能 C：AI 返回的 JSON 中 entry_id 不匹配**
```kotlin
// AndroidAiTranslationService.kt — 响应解析
// 如果 AI 返回的是编号（0、1、2）而不是 entry_id
// 前端按 entry_id 查找但找不到，翻译「看似不生效」
```

### 修复

```kotlin
// AndroidAiTranslationService.kt — response 解析改进
private fun parseResponse(responseBody: String, entries: JSONArray): JSONArray {
    val translations = JSONArray()
    val json = JSONObject(responseBody)
    
    // DeepSeek / OpenAI 格式
    val choices = json.optJSONArray("choices")
    if (choices != null && choices.length() > 0) {
        val content = choices.getJSONObject(0)
            .optJSONObject("message")
            ?.optString("content", "") ?: ""
        
        // 尝试解析 AI 返回的 JSON
        try {
            val resultJson = JSONObject(content)
            for (i in 0 until entries.length()) {
                val entry = entries.getJSONObject(i)
                val entryId = entry.optString("entry_id", "")
                val source = entry.optString("source", "")
                
                // 按 entry_id 匹配
                var target = resultJson.optString(entryId, "")
                // fallback: 按索引匹配
                if (target.isBlank()) {
                    target = resultJson.optString(i.toString(), "")
                }
                // fallback: 按原文匹配
                if (target.isBlank()) {
                    val iter = resultJson.keys()
                    while (iter.hasNext()) {
                        val key = iter.next()
                        if (resultJson.optString(key, "") == source) {
                            target = key
                            break
                        }
                    }
                }
                
                translations.put(JSONObject().apply {
                    put("entry_id", entryId)
                    put("source", source)
                    put("target", target)
                })
            }
        } catch (e: Exception) {
            // AI 返回的不是 JSON，可能是纯文本列表
            val lines = content.split("\n").filter { it.contains("->") || it.contains("=") || it.contains(":") }
            for (i in 0 until minOf(lines.size, entries.length())) {
                val entry = entries.getJSONObject(i)
                val parts = lines[i].split(Regex("->|=|:"), limit = 2)
                val target = if (parts.size >= 2) parts[1].trim().removeSurrounding("\"") else ""
                translations.put(JSONObject().apply {
                    put("entry_id", entry.optString("entry_id", ""))
                    put("source", entry.optString("source", ""))
                    put("target", target)
                })
            }
        }
    }
    
    // 豆包 / 小米 / 其他格式
    val responseText = when {
        json.has("response") -> json.optString("response", "")
        json.has("text") -> json.optString("text", "")
        json.has("output") -> json.optString("output", "")
        else -> json.optString("content", "")
    }
    
    return translations
}
```

```typescript
// pages/translate/translate.vue — 增加详细错误显示
async function runAi() {
  const settings = ai.value
  uni.setStorageSync('ai_settings', settings)
  
  // 首先检查 API Key
  if (!settings.apiKey?.trim()) {
    uni.showModal({ title: '翻译失败', content: '请在 AI 设置中填写 API Key' })
    return
  }
  
  uni.showLoading({ title: '翻译中...' })
  const result = await translation.translateVisible({ ...settings, range: translation.range })
  uni.hideLoading()
  
  if (result.error) {
    uni.showModal({ title: '翻译出错', content: result.error })
  } else if (result === 0) {
    uni.showToast({ title: '没有待翻译文本', icon: 'none' })
  } else {
    uni.showToast({ title: `已翻译 ${result} 条`, icon: 'success' })
  }
}
```

```typescript
// store/translation.ts — translateVisible 返回错误
async function translateVisible(settings: Record<string, any>) {
  const targets = filtered.value.filter(e => !String(e.target || '').trim())
  if (!targets.length) return 0 as any
  
  loading.value = true
  error.value = ''
  let done = 0
  
  try {
    for (let i = 0; i < targets.length; i += 50) {
      const chunk = targets.slice(i, i + 50)
      const result = await translateApi.aiTranslate(settings, chunk)
      
      if (result.error) {
        error.value = result.error
        return { count: done, error: result.error }
      }
      
      // 按 entry_id 或 source 匹配写回
      ;(result.translations || []).forEach((item: any) => {
        const original = entries.value.find(
          (e: any) => e.entry_id === item.entry_id || e.source === item.source
        )
        if (original && item.target) original.target = item.target
      })
      
      done += chunk.length
      doneCount.value = done
    }
    
    return done as any
  } catch (e: any) {
    error.value = e.message || '翻译请求失败'
    return { count: done, error: error.value }
  } finally {
    loading.value = false
  }
}
```

---

## Bug 5：虚拟按键只有数值没有标签

### 根因（已追溯）

`settings.vue` 的虚拟按键编辑面板中，每个按键显示 `x: 0.5, y: 0.5, size: 50, opacity: 0.65` 等原始数值，**但编辑器 UI 没有对这些字段显示中文标签**。新增按键时默认 label='X' 但编辑器里 label 字段是唯一带 placeholder 的输入框，而 x/y/size/opacity 字段只有 raw 数字输入框，用户看不懂每个数字是什么意思。

### 修复

```vue
<!-- settings.vue — 按键编辑面板增加中文标签 -->
<!-- 当前代码类似于： -->
<input class="input" v-model.number="selected.x" type="number" step="0.01" placeholder="X" />
<input class="input" v-model.number="selected.y" type="number" step="0.01" placeholder="Y" />

<!-- 改为： -->
<view class="field-group">
  <text class="field-label">X 位置 (0~1)</text>
  <input class="input" v-model.number="selected.x" type="number" step="0.01" placeholder="0.5" />
</view>
<view class="field-group">
  <text class="field-label">Y 位置 (0~1)</text>
  <input class="input" v-model.number="selected.y" type="number" step="0.01" placeholder="0.5" />
</view>
<view class="field-group">
  <text class="field-label">大小</text>
  <slider :value="selected.size" min="10" max="150" 
    @change="selected.size = $event.detail.value" show-value />
</view>
<view class="field-group">
  <text class="field-label">透明度</text>
  <slider :value="selected.opacity * 100" min="10" max="100"
    @change="selected.opacity = $event.detail.value / 100" show-value />
</view>
```

```vue
<!-- 按键列表显示也加标签 -->
<view v-for="btn in buttons" :key="btn.id" class="btn-item">
  <text class="btn-label">{{ btn.label || '未命名' }}</text>
  <text class="btn-meta">键码: {{ btn.keyCode }} | 位置: ({{ btn.x }}, {{ btn.y }})</text>
</view>
```

---

## Bug 6：兼容模式放错位置

### 根因（已追溯）

`settings.vue` 中「快速模式」和「兼容模式」按钮放在第一个面板顶部的 `launch-box` 中，而这个面板同时也是**虚拟按键控制器编辑区**。兼容模式是游戏启动设置，不应该和按键布局编辑混在一起。

### 修复

```vue
<!-- settings.vue — 把启动模式移到独立的「启动设置」面板 -->

<!-- 方案：在页面顶部新增一个独立的启动设置面板 -->
<view class="panel">
  <view class="panel-title">启动设置</view>
  <view class="launch-box">
    <view class="row">
      <button class="button" :class="{ active: gameMode === 'fast' }"
        @tap="setMode('fast')">快速模式</button>
      <button class="button" :class="{ active: gameMode === 'compat' }"
        @tap="setMode('compat')">兼容模式</button>
      <label class="check">
        <checkbox :checked="vfsInject" @tap="vfsInject = !vfsInject" />
        VFS 翻译注入
      </label>
    </view>
    <view class="status">{{ modeHint }}</view>
  </view>
</view>

<!-- 再下面才是虚拟按键控制器编辑面板 -->
<view class="panel">
  <view class="panel-title">按键布局编辑</view>
  <!-- 原有的虚拟按键代码... -->
</view>
```

```diff
// 同时更新 setMode 函数
- function setMode(mode) { ... }  // 原有
+ function setMode(mode) {
+   gameMode.value = mode
+   uni.setStorageSync('game_mode', mode)
+   modeHint.value = mode === 'fast' 
+     ? '快速模式：使用 WebView 直接加载游戏'
+     : '兼容模式：使用内置 Wine 引擎运行 Windows exe'
+ }
```

---

## 修复优先级

| 优先级 | Bug | 根因 | 改动量 |
|---|---|---|---|
| 🔴 P0 | 存档不读游戏存档 | `SAVE_FILE_REGEX` 只匹配 "file" 不匹配 "Save" | 改 1 行正则 |
| 🔴 P0 | 列表只能显示 30 条 | `limit` 参数传递链路断裂，某处变成 0 | Kotlin +3 行 |
| 🟡 P1 | 键盘弹出缩放 | `interactive-widget=resizes-content` 与 scale 锁定冲突 | HTML +5 行 |
| 🟡 P1 | 汉化无法翻译 | API Key/网络/entry_id 不匹配 | Kotlin +30 行 |
| 🟢 P2 | 虚拟按键无中文标签 | 编辑器只有 raw 数值没文字说明 | Vue +30 行 |
| 🟢 P2 | 兼容模式放错位置 | 启动设置和按键编辑混在一个面板 | Vue +20 行 |

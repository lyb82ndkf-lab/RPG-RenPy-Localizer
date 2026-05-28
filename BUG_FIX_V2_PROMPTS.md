# Bug 修复提示词 — 根本原因驱动的修复

---

## Bug 1：存档位置仍然错误（www/save 找不到）

### 根本原因（已定位）

`MainActivity.kt:714-728` 的 `androidGetSavePath()` 硬编码了 `"save"` 作为存档路径，完全忽略了 `AndroidRpgMakerService.findSaveDirs()` 实际找到的目录：

```kotlin
// MainActivity.kt — 错误的代码
fun androidGetSavePath(): String {
    if (isWineContext()) {
        return WineSaveService(this).savePath(externalContainerId, externalGamePath).toString()
    }
    return androidRpgServiceResult { service ->
        val slots = service.saveSlots()  // 这里正确扫描了 www/save
        JSONObject()
            .put("ok", true)
            .put("exists", slots.optInt("count", 0) > 0)
            .put("savePath", "save")      // ← 硬编码！应该用 findSaveDirs() 返回的真实路径
    }
}
```

而 `AndroidRpgMakerService.findSaveDirs()` 确实扫描了 `www/save`、`save`、`game/saves` 等路径，但结果没有被 `androidGetSavePath()` 使用。

### 修复

```kotlin
// MainActivity.kt — androidGetSavePath()
fun androidGetSavePath(): String {
    if (isWineContext()) {
        return WineSaveService(this).savePath(externalContainerId, externalGamePath).toString()
    }
    return androidRpgServiceResult { service ->
        // 找到真实的存档目录
        val saveDirs = service.findSaveDirs()
        val realSavePath = if (saveDirs.isNotEmpty()) {
            saveDirs.first().uri.toString()
        } else {
            "save"  // fallback
        }
        val slots = service.saveSlots()
        JSONObject()
            .put("ok", true)
            .put("exists", slots.optInt("count", 0) > 0)
            .put("savePath", realSavePath)        // ← 使用真实路径
            .put("directories", saveDirs.map { it.uri })  // 列出所有找到的存档目录
    }
}
```

```kotlin
// AndroidRpgMakerService.kt — 确保 findSaveDirs() 是 public
// 或者新增一个公开方法：
fun getDefaultSaveDir(): String? {
    return findSaveDirs().firstOrNull()?.uri?.toString()
}
```

### 验证方法
1. 打开游戏目录含 `www/save/` 的游戏
2. 进入存档页 → 确认存档路径显示为 `www/save/` 而非 `save/`
3. 新建存档 → 文件出现在 `www/save/` 目录下

---

## Bug 2：翻译页不显示原文、「开始翻译」按钮失效

### 根本原因（已定位）

`translate.vue` 的 AI 翻译按钮是存在的（`"AI 翻译当前筛选"`），但用户看不到效果。原因可能有三层：

#### 第一层：翻译条目加载可能失败

```typescript
// api/translate.ts
export function listEntries(limit = 5000) {
  if (isAndroidShell()) return Promise.resolve(
    shellJson<{ entries: TranslationEntry[]; count: number }>('androidTranslationEntries', limit)
  )
  // ...
}
```

**检查点**：需要验证 `androidTranslationEntries` 实际返回了什么。

```kotlin
// Kotlin 侧 — 需要加日志
@JavascriptInterface
fun androidTranslationEntries(limit: Int): String {
    val result = androidRpgServiceResult { service ->
        val entries = service.translationEntries(null, null)
        val truncated = if (limit > 0 && entries.length() > limit) {
            JSONArray(entries.toList().subList(0, limit))
        } else entries
        JSONObject().put("entries", truncated).put("count", entries.length())
    }
    // ★ 加日志调试
    Log.d("TRANSLATION", "androidTranslationEntries(limit=$limit) returned ${result.optInt("count", 0)} entries")
    return result.toString()
}
```

#### 第二层：`translationEntries()` 可能返回空

检查 `AndroidRpgMakerService.translationEntries()` 是否确实从 `www/data/` 中的 JSON 文件提取了字符串：

```kotlin
// AndroidRpgMakerService.kt — 检查 extractStrings 递归
private fun extractStrings(data: JSONObject, sourceFile: String, entries: JSONArray, prefix: String = "") {
    val iter = data.keys()
    while (iter.hasNext()) {
        val key = iter.next()
        val value = data.opt(key)
        when (value) {
            is String -> {
                // ★ 只跳过 metadata 字段，保留 name/description/note 等文本
                if (SKIP_DATA_KEYS.contains(key)) continue
                if (value.length < 2 || value.all { it.isWhitespace() }) continue
                entries.put(JSONObject().apply {
                    put("entry_id", "$sourceFile:$prefix$key")
                    put("source", value)
                    put("target", "")
                    put("file", sourceFile)
                })
            }
            is JSONObject -> extractStrings(value, sourceFile, entries, "$prefix$key/")
            is JSONArray -> {
                for (i in 0 until value.length()) {
                    val item = value.opt(i)
                    if (item is JSONObject) extractStrings(item, sourceFile, entries, "$prefix$key[$i]/")
                    else if (item is String) {
                        if (SKIP_DATA_KEYS.contains(key)) continue
                        entries.put(JSONObject().apply {
                            put("entry_id", "$sourceFile:$prefix$key[$i]")
                            put("source", item)
                            put("target", "")
                            put("file", sourceFile)
                        })
                    }
                }
            }
        }
    }
}
```

#### 第三层：SKIP_DATA_KEYS 误过滤

```kotlin
// ★ 确认这个集合不含 name/description/note 等文本字段
private val SKIP_DATA_KEYS = setOf(
    "id", "iconIndex", "animationId", "hit", "weaponImageId",
    "partyImageId", "characterIndex", "characterImage",
    "battlerUv", "height", "width", "scrollX", "scrollY",
    "blockX", "blockY", "moveSpeed", "moveFrequency",
    "priorityType", "trigger",
    // ★ 不允许跳过 text/name/description/note/displayName/fullName/shortName！
)
```

### 修复：翻译页增加统计 + 强制测试按钮

```diff
// pages/translate/translate.vue — 增加统计显示和强制重置
+ <view class="stats-bar">
+   <text class="stat-item">共 {{ entries.length }} 条</text>
+   <text class="stat-item split">|</text>
+   <text class="stat-item translated">已译 {{ translatedCount }}</text>
+   <text class="stat-item split">|</text>
+   <text class="stat-item untranslated">未译 {{ untranslatedCount }}</text>
+ </view>
+ 
+ <button class="button secondary" @tap="forceReload">🔄 重新加载原文</button>
+ <button class="button primary" :disabled="translation.loading" @tap="runAi">
+   {{ translation.loading ? '翻译中...' : '▶ 开始翻译' }}
+ </button>
+ <button class="button" @tap="showSettings">⚙️ AI 设置</button>
```

```typescript
// pages/translate/translate.vue — script 部分
const translation = useTranslationStore()

const entries = computed(() => translation.entries)
const translatedCount = computed(() => entries.value.filter(e => String(e.target || '').trim()).length)
const untranslatedCount = computed(() => entries.value.filter(e => !String(e.target || '').trim()).length)

async function forceReload() {
  uni.showLoading({ title: '加载原文...' })
  await translation.load(5000, true)  // forceRefresh = true
  uni.hideLoading()
  uni.showToast({ title: `已加载 ${entries.value.length} 条原文`, icon: 'none' })
}
```

```typescript
// store/translation.ts — 暴露统计
+ const translatedCount = computed(() => 
+   entries.value.filter(e => String(e.target || '').trim()).length
+ )
+ const untranslatedCount = computed(() =>
+   entries.value.filter(e => !String(e.target || '').trim()).length
+ )
```

```vue
<!-- translation.vue — 样式 -->
<style scoped>
.stats-bar {
  display: flex; justify-content: center; align-items: center;
  gap: 8px; padding: 8px 0;
}
.stat-item { font-size: 13px; }
.stat-item.translated { color: #4CAF50; }
.stat-item.untranslated { color: #FF9800; }
.stat-item.split { color: #555; }
</style>
```

### 验证方法
1. 进入翻译页 → 看到 `共 1246 条 | 已译 0 | 未译 1246`
2. 点击 「▶ 开始翻译」 → 进度条前进
3. 翻译完成后 → `已译 20 | 未译 1226`

---

## Bug 3：输入法弹出时界面缩放

### 根本原因（已定位）

`index.html:9-10` 的 viewport meta 标签与 UniApp WebView 的交互问题：

```html
<meta name="viewport" content="width=device-width, user-scalable=no,
  initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0,
  interactive-widget=overlays-content" />
```

原因链：
1. `interactive-widget=overlays-content` 告诉 WebView 键盘应该覆盖内容而非调整视口
2. 但 UniApp 内部使用 `<scroll-view>` 组件，当键盘弹出时焦点元素试图滚动到可视区域
3. 部分 Android WebView 实现在 `user-scalable=no` 且键盘弹出时，会错误地放大焦点区域
4. `uni.scss` 中输入框的 `transform: scale(0.82)` 加剧了这个问题：缩放后的输入框实际尺寸与 WebView 计算的尺寸不一致，键盘弹出时 WebView 尝试对齐导致缩放

### 修复

#### 方案 A：修改 viewport 元标签（最有效）

```diff
- <meta name="viewport" content="width=device-width, user-scalable=no,
-   initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0,
-   interactive-widget=overlays-content" />
+ <meta name="viewport" content="width=device-width, initial-scale=1.0,
+   maximum-scale=5.0, user-scalable=yes,
+   interactive-widget=resizes-content" />
```

改动：
- `user-scalable=no` → `user-scalable=yes` + `maximum-scale=5.0`：允许缩放但通过 JS 禁止捏合
- `interactive-widget=overlays-content` → `interactive-widget=resizes-content`：键盘弹出时调整视口而非叠加

后面在 JS 中阻止用户捏合缩放：

```typescript
// main.js 或 App.vue
document.addEventListener('gesturestart', function(e) { e.preventDefault() })
document.addEventListener('touchmove', function(e) {
  if (e.touches.length >= 2) e.preventDefault()
}, { passive: false })
```

#### 方案 B：移除输入框的 transform: scale（配合方案A用）

```diff
// uni.scss
.input {
  ...
-  transform: scale(0.82);
-  transform-origin: left center;
-  width: 122%;
+  font-size: 13px;  // 直接用小字号代替缩放
}
```

#### 方案 C：键盘弹出时锁定窗口尺寸（强力方案）

```typescript
// pages/translate/translate.vue 或 App.vue
// 监听键盘弹出事件，锁定窗口尺寸
let originalHeight = 0

uni.onKeyboardHeightChange(({ height }) => {
  if (height > 0) {
    // 键盘弹出：固定窗口高度
    if (originalHeight === 0) {
      originalHeight = window.innerHeight
    }
    document.body.style.height = originalHeight + 'px'
    document.documentElement.style.height = originalHeight + 'px'
  } else {
    // 键盘收起：恢复自动高度
    document.body.style.height = ''
    document.documentElement.style.height = ''
    originalHeight = 0
  }
})
```

### 验证方法
1. 进入翻译页或数据编辑页
2. 点击任意输入框 → 键盘弹出
3. 确认页面没有缩放/跳动
4. 输入文字 → 确认内容显示正确
5. 关闭键盘 → 恢复到初始状态

---

## 修复优先级与工作量

| 优先级 | Bug | 根因 | 修复方式 | 行数 |
|---|---|---|---|---|
| 🔴 P0 | 存档路径硬编码 | `androidGetSavePath()` 返回 `"save"` 而非真实路径 | 用 `findSaveDirs()` 的结果 | Kotlin +10 行 |
| 🔴 P0 | 翻译页无统计/无法启动 | 统计字段未暴露、`translationEntries` 可能返回空 | 加统计 + 强制重载按钮 | Vue +40 行 |
| 🟡 P1 | 键盘弹出缩放 | `interactive-widget=overlays-content` + `transform:scale` 冲突 | viewport 改 `resizes-content` + 移除 scale | HTML +5 行 |

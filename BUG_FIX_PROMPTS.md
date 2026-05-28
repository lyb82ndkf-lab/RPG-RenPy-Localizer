# Bug 修复提示词（给 Codex）

---

## Bug 1：数据编辑器左侧列表只能滚动到 30 条

### 症状
角色/物品/装备/防具等数据编辑页，左侧分组列表只能下滑约 30 条，不能看到所有数据。

### 根因
`androidDataRecords()` 的默认 `limit` 是 `500`，但它是**总标量记录数**的限制，不是分组数。每个角色有 ~10 个标量字段（name、hp、mp、atk 等），500 条限制 ÷ 10 ≈ 50 个角色。对于大型游戏（100+ 角色、500+ 物品），这个限制远远不够。

```kotlin
// AndroidRpgMakerService.kt
fun androidDataRecords(category: String, limit: Int): String {
    // limit 默认 500 — 这是标量记录总数，不是分组数
    return cachedAndroidRpgResult("records:$category:$limit") { service ->
        service.dataRecords(category, limit)
    }
}
```

### 修复方案

#### 方案 A：增加默认 limit（最快）

```diff
- const limit = 500;
+ const limit = 5000;  // 提高 10 倍
```

在 UniApp 前端调用处改：

```typescript
// api/data.ts
const result = await bridge('androidDataRecords', [category, 5000]);
```

#### 方案 B：分页加载（更彻底但改动大）

在后端 `dataRecords()` 中支持 `offset` + `pageSize`，前端滚动时请求下一页。

#### 方案 C：前端 DataTable 虚拟滚动（最彻底）

重写 DataTable 用虚拟列表（只渲染可见行），不限制总数。

**建议选方案 A**（改一行配置，3 分钟解决），后续再做方案 C。

```diff
// store/data.ts 中 load() 调用
- const data = await bridge('androidDataRecords', [category.value]);
+ const data = await bridge('androidDataRecords', [category.value, 5000]);
```

---

## Bug 2：翻译页面不显示待翻译原文

### 症状
进入翻译页，原文列表为空或显示「未找到待翻译文本」。

### 根因
翻译数据加载流程：

```
translate.vue 加载 → store/translation.ts:load()
  → api/translate.ts listEntries()
    → bridge('androidTranslationEntries', [category, query?])
      → AndroidRpgMakerService:translationEntries()
```

问题可能出在：

1. **`translationEntries()` 的类别过滤不对** — RPG Maker MV 的 JSON 结构遍历深度不够
2. **`SKIP_DATA_KEYS` 误过滤了文本字段** — `note`、`description` 等字段被跳过
3. **浏览器端（非 Android）路由走 HTTP**，但后端未启动

### 修复提示

```kotlin
// AndroidRpgMakerService.kt — 检查 translationEntries 函数

fun translationEntries(category: String?, query: String?): JSONObject {
    val entries = JSONArray()
    
    for (file in sortedJsonFiles()) {
        val name = file.name ?: continue
        // category 过滤：空=全部，Maps=地图，MapInfos=地图名，其他=对应 DB 文件
        if (category != null && !category.isNullOrBlank()) {
            // ★ 确认类别映射正确
            // Actors.json → "角色"
            // Items.json → "物品"
            // 等等
        }
        
        val data = readJson(file) ?: continue
        
        // ★ 递归遍历，提取所有 String 值
        // SKIP_DATA_KEYS 不应该包含 'name'、'description'、'note' 等文本字段
        extractStrings(data, name, entries)
    }
    
    return JSONObject().put("entries", entries)
}

// 检查 SKIP_DATA_KEYS
private val SKIP_DATA_KEYS = setOf(
    "id", "iconIndex", "animationId", "hit", "weaponImageId", 
    "partyImageId", "characterIndex", "characterImage", 
    "battlerUv", "height", "width", "scrollX", "scrollY", "blockX", "blockY",
    "moveSpeed", "moveFrequency", "priorityType", "trigger",
    // ★ 不应该跳过 text/name/description/note！
)
```

**建议**：打印日志看 `translationEntries` 返回了多少条。在 Kotlin 中加日志：

```kotlin
Log.d("TRANSLATE", "Found ${entries.length()} entries from $name")
```

然后在 logcat 查看 `adb logcat -s TRANSLATE`。

---

## Bug 3：AI 翻译无法真正执行

### 症状
点击「AI 翻译当前筛选」按钮没有响应、报错、或翻译不生效。

### 根因
前端调用链是通的，但问题可能在：

1. **API Key 或模型配置已过期**
2. **AndroidAiTranslationService 返回错误但前端没显示**
3. **翻译结果写入失败** — `updateRecord` 无法写回

### 修复提示

#### 3a：增加 AI 翻译错误反馈

```kotlin
// AndroidAiTranslationService.kt
// 确保所有错误都返回给前端

try {
    val response = httpClient.newCall(request).execute()
    if (!response.isSuccessful) {
        val errorBody = response.body?.string() ?: "unknown"
        return JSONObject().apply {
            put("error", "API 返回 ${response.code}: $errorBody")
        }
    }
    // ... 解析响应
} catch (e: Exception) {
    return JSONObject().apply {
        put("error", "网络错误: ${e.message}")
    }
}
```

#### 3b：前端显示错误

```typescript
// store/translation.ts — translateVisible 函数
const result = await translateApi.aiTranslate(settings, chunk)
if (result.error) {
  error.value = result.error  // 显示给用户
  break
}
```

#### 3c：确认 DeepSeek/OpenAI URL 配置正确

```diff
// utils/constants.ts
const AI_PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek', 
    baseUrl: 'https://api.deepseek.com',        // ← 确认没被墙
    model: 'deepseek-chat' },
  { value: 'doubao', label: '豆包 Ark',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',  // ← 国内可用
    model: 'doubao-seed-2-0-mini-250715' },
  // ...
]
```

---

## Bug 4：翻译页面缺少配置项（小米 cluster、进度条等）

### 症状
- 小米 Token Plan 没有 `cluster`（cn/sgp/ams）配置
- 翻译时没有进度条
- 比 PC 版少很多设置项

### 修复提示

#### 4a：增加小米 cluster 配置

```diff
// components/AiSettings.vue
- <input class="input" v-model="form.model" placeholder="模型" />
+ <input class="input" v-model="form.model" placeholder="模型" />
+ <!-- 小米 Token Plan 专有：cluster -->
+ <input v-if="form.provider === 'xiaomi_token_plan'" 
+   class="input" v-model="form.cluster" placeholder="集群 (cn/sgp/ams)" />
```

```diff
// AndroidAiTranslationService.kt — 构造请求时加上 cluster
+ val cluster = settings.optString("cluster", "sgp")
+ // ... 加到 URL 或 body
```

#### 4b：增加翻译进度条

```vue
<!-- pages/translate/translate.vue — 在翻译按钮下方 -->
<progress v-if="translation.loading" 
  :percent="translation.progress" 
  stroke-width="3" 
  activeColor="#4CAF50"
/>
```

```typescript
// store/translation.ts
const progress = ref(0)
const totalToTranslate = ref(0)

async function translateVisible(settings: Record<string, any>) {
  const targets = filtered.value.filter(e => !String(e.target || '').trim())
  totalToTranslate.value = targets.length
  progress.value = 0
  
  for (let i = 0; i < targets.length; i += 20) {
    // ... 翻译 ...
    progress.value = Math.round((i + chunk.length) / totalToTranslate.value * 100)
  }
}
```

#### 4c：增加「测试连接」按钮

```vue
<!-- AiSettings.vue — 保存按钮旁边 -->
<button class="button secondary" @tap="testConnection">测试连接</button>
```

```typescript
async function testConnection() {
  loading.value = true
  try {
    const result = await bridge('androidAiTranslate', [JSON.stringify({
      settings: form, entries: [{ source: '你好世界', entry_id: 'test' }]
    })])
    uni.showToast({ title: result?.translations ? '✅ 连接成功' : '⚠️ 返回异常', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: '❌ 连接失败: ' + e.message, icon: 'none' })
  } finally { loading.value = false }
}
```

#### 4d：增加 temperature / top_p / max_tokens 控制

```vue
<!-- AiSettings.vue — 高级设置折叠面板 -->
<view class="advanced-toggle" @tap="showAdvanced = !showAdvanced">
  高级设置 {{ showAdvanced ? '▲' : '▼' }}
</view>
<view v-if="showAdvanced" class="advanced-panel">
  <text>Temperature: {{ form.temperature || 0.2 }}</text>
  <slider :value="form.temperature || 0.2" min="0" max="1" step="0.1"
    @change="form.temperature = $event.detail.value" />
  
  <text>Top P: {{ form.top_p || 0.9 }}</text>
  <slider :value="form.top_p || 0.9" min="0" max="1" step="0.1"
    @change="form.top_p = $event.detail.value" />
  
  <text>Max Tokens: {{ form.max_tokens || 8192 }}</text>
  <slider :value="Math.log2((form.max_tokens || 8192)/256)" min="4" max="8" step="1"
    @change="form.max_tokens = Math.pow(2, $event.detail.value + 8)" />
</view>
```

---

## Bug 5：翻译结果「嵌入游戏文本」功能缺失

### 症状
PC 版可以把翻译结果直接写回游戏文件（embedded mode），Android 版没有这个入口。

### 根因
Android 版 `api/translate.ts` 的 `saveEntries()` 调用了 `bridge('androidUpdateRecord')`，但只支持单条更新，没有批量「写入全部并替换游戏文件」的功能。

### 修复提示

```kotlin
// AndroidRpgMakerService.kt — 新增批量写入方法

@JavascriptInterface
fun androidSaveTranslationEntries(json: String): String {
    val request = JSONObject(json)
    val entries = request.getJSONArray("entries")
    val mode = request.optString("mode", "replace")  // replace / embed
    
    // 按文件分组
    val byFile = mutableMapOf<String, JSONArray>()
    for (i in 0 until entries.length()) {
        val entry = entries.getJSONObject(i)
        val file = entry.optString("file", "")
        if (file.isBlank()) continue
        if (!byFile.containsKey(file)) byFile[file] = JSONArray()
        byFile[file]!!.put(entry)
    }
    
    // 逐个文件写回
    for ((file, fileEntries) in byFile) {
        val dataFile = dataDir.findFile(file) ?: continue
        var data = readJson(dataFile) ?: continue
        
        for (i in 0 until fileEntries.length()) {
            val entry = fileEntries.getJSONObject(i)
            val path = entry.getJSONArray("json_path")
            val target = entry.optString("target", "")
            
            // 沿 json_path 定位并写入
            var node = data
            for (j in 0 until path.length() - 1) {
                node = childAt(node, path.get(j)) ?: break
            }
            if (node != null) {
                val lastKey = path.get(path.length() - 1)
                setChild(node, lastKey, target)
            }
        }
        
        // 写回文件
        backupFile(dataFile, "translation")
        writeText(dataFile, jsonToString(data))
    }
    
    return JSONObject().put("ok", true).put("count", entries.length())
}
```

---

## Bug 6：翻译页面缺少进度指示（整体进度条）

### 症状
翻译一批文本时，用户不知道翻译了多少、还要多久。

### 修复提示

```vue
<!-- pages/translate/translate.vue — 翻译工作台顶部 -->
<view class="progress-bar" v-if="translation.loading">
  <view class="progress-fill" :style="{ width: translation.progress + '%' }" />
  <text class="progress-text">
    {{ translation.doneCount }}/{{ translation.totalCount }} 条
  </text>
</view>
```

```typescript
// store/translation.ts
const doneCount = ref(0)
const totalCount = ref(0)
const progress = computed(() => 
  totalCount.value > 0 ? Math.round(doneCount.value / totalCount.value * 100) : 0
)

async function translateVisible(settings: Record<string, any>) {
  const targets = filtered.value.filter(e => !String(e.target || '').trim())
  totalCount.value = targets.length
  doneCount.value = 0
  
  for (let i = 0; i < targets.length; i += 20) {
    const chunk = targets.slice(i, i + 20)
    // ... 请求翻译 ...
    doneCount.value += chunk.length
  }
}
```

---

## 修复优先级

| 优先级 | Bug | 影响 | 改动量 |
|---|---|---|---|
| 🔴 P0 | 列表只能滚动 30 条（Bug 1） | 用户看不到完整数据 | 改 1 行 |
| 🔴 P0 | 翻译不显示原文（Bug 2） | 翻译完全不可用 | 半天排查 |
| 🔴 P0 | AI 翻译不执行（Bug 3） | 翻译功能废掉 | 半天排查 |
| 🟡 P1 | 缺少 cluster/进度条（Bug 4） | 体验差但不致命 | 半天 |
| 🟡 P1 | 无法批量写回翻译（Bug 5） | 翻译无法保存 | 半天 |
| 🟢 P2 | 缺少进度指示（Bug 6） | 体验差 | 0.5 天 |

**建议先修 P0 的三个**，然后 P1。

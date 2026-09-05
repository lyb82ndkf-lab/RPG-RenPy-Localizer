<template>
  <div class="app-page translations-view">
    <section class="app-hero">
      <div>
        <span class="eyebrow">TRANSLATION WORKBENCH</span>
        <h2>翻译工作台</h2>
        <p>支持文本检索筛选、单句手动修改、AI 单句与批量翻译、实时汉化监控。</p>
      </div>
      <div class="hero-actions">
        <button class="app-button primary" :disabled="loading" @click="loadEntries">
          {{ loading ? '载入中...' : '载入/刷新文本' }}
        </button>
      </div>
    </section>

    <!-- 统计指标 -->
    <section class="stat-grid translation-stat-grid">
      <article class="stat-card"><span>文本总数</span><strong>{{ totalCount }}</strong></article>
      <article class="stat-card"><span>已翻译</span><strong>{{ doneCount }}</strong></article>
      <article class="stat-card"><span>待翻译</span><strong>{{ missingCount }}</strong></article>
      <article class="stat-card"><span>完成度</span><strong>{{ progressPercent }}%</strong></article>
    </section>

    <!-- 进度面板 -->
    <section class="progress-panel">
      <div class="progress-head">
        <strong>{{ progress.message || (totalCount ? `共 ${totalCount} 条文本` : '等待载入文本') }}</strong>
        <span>{{ doneCount }} / {{ totalCount }}</span>
      </div>
      <div class="progress-track"><i :style="{ width: progressPercent + '%' }"></i></div>
    </section>

    <!-- 批量翻译与保存按钮 -->
    <section class="action-panel two-actions">
      <button class="app-button primary" :disabled="aiBusy || !missingCount" @click="translateMissing">
        {{ aiBusy ? 'AI 正在批量翻译...' : '开始翻译未翻译项' }}
      </button>
      <button class="app-button" :disabled="!dirtyCount" @click="saveTranslations">
        保存全部译文 {{ dirtyCount ? `(${dirtyCount})` : '' }}
      </button>
    </section>

    <!-- 实时汉化状态 -->
    <section class="settings-panel">
      <div class="panel-head-row">
        <div>
          <h3>Ren'Py 实时汉化状态</h3>
          <p class="muted">{{ liveStatus.message || '运行 Ren’Py 游戏时将自动建立 Hook 管道。' }}</p>
        </div>
        <button class="app-button small" @click="refreshLiveStatus">刷新实时状态</button>
      </div>

      <label class="setting-switch">
        <div>
          <strong>{{ liveEnabled ? '已开启实时汉化' : '已关闭实时汉化' }}</strong>
          <p>控制游戏内是否自动拦截新对话并注入翻译。</p>
        </div>
        <input type="checkbox" :checked="liveEnabled" @change="setLiveEnabled($event.target.checked)" />
      </label>

      <div class="stat-grid translation-stat-grid live-stat-grid">
        <article class="stat-card"><span>Hook 连接</span><strong>{{ liveStatus.connected ? '已连接' : (liveStatus.running ? '等待中' : '未运行') }}</strong></article>
        <article class="stat-card"><span>捕获台词</span><strong>{{ liveStatus.captured || 0 }}</strong></article>
        <article class="stat-card"><span>实时已译</span><strong>{{ liveStatus.translated || 0 }}</strong></article>
        <article class="stat-card"><span>缓存条数</span><strong>{{ liveStatus.cached || 0 }}</strong></article>
      </div>
    </section>

    <!-- 文本检索与筛选列表 -->
    <section class="settings-panel list-panel">
      <div class="list-filter-bar">
        <input v-model="searchKeyword" placeholder="搜索原文或译文关键词..." class="search-input" />
        <div class="filter-chips">
          <button class="chip-btn" :class="{ active: filterMode === 'all' }" @click="filterMode = 'all'">全部 ({{ translations.length }})</button>
          <button class="chip-btn" :class="{ active: filterMode === 'missing' }" @click="filterMode = 'missing'">待翻译 ({{ missingItemsCount }})</button>
          <button class="chip-btn" :class="{ active: filterMode === 'done' }" @click="filterMode = 'done'">已翻译 ({{ doneItemsCount }})</button>
        </div>
      </div>

      <!-- 分页控制 -->
      <div v-if="filteredEntries.length > pageSize" class="pagination-bar">
        <button class="app-button small" :disabled="currentPage <= 1" @click="currentPage--">上一页</button>
        <span>第 {{ currentPage }} / {{ totalPages }} 页 (共 {{ filteredEntries.length }} 条)</span>
        <button class="app-button small" :disabled="currentPage >= totalPages" @click="currentPage++">下一页</button>
      </div>

      <!-- 条目列表 -->
      <div class="translation-list">
        <article
          v-for="item in pagedEntries"
          :key="item.entry_id || item.id"
          class="translation-card"
          :class="{ selected: selectedEntry?.entry_id === item.entry_id }"
          @click="selectItem(item)"
        >
          <div class="card-meta">
            <span class="entry-tag">#{{ item.entry_id || item.id }}</span>
            <span class="status-pill" :class="{ translated: Boolean(item.target?.trim()) }">
              {{ item.target?.trim() ? '已翻译' : '待翻译' }}
            </span>
          </div>
          <p class="source-text">{{ item.source || item.original || '—' }}</p>
          <p class="target-text" :class="{ empty: !item.target?.trim() }">
            {{ item.target?.trim() || '（暂无译文，点击编辑）' }}
          </p>
        </article>

        <div v-if="!filteredEntries.length" class="empty-list">
          <p>{{ translations.length ? '没有匹配的文本条目。' : '尚未载入文本，请点击上方「载入/刷新文本」。' }}</p>
        </div>
      </div>
    </section>

    <!-- 单句编辑弹窗 / 浮层 -->
    <div v-if="selectedEntry" class="edit-dialog-overlay" @click.self="selectedEntry = null">
      <div class="edit-card">
        <div class="edit-card-header">
          <div>
            <h3>编辑译文 #{{ selectedEntry.entry_id || selectedEntry.id }}</h3>
            <small class="muted">支持手动输入或单句调用当前配置的 AI 模型</small>
          </div>
          <button class="close-btn" @click="selectedEntry = null">×</button>
        </div>

        <label>原文</label>
        <textarea :value="selectedEntry.source || selectedEntry.original" rows="3" readonly class="readonly-area"></textarea>

        <label>译文</label>
        <textarea v-model="draftTarget" rows="4" placeholder="在此输入译文..."></textarea>

        <div class="edit-actions">
          <button class="app-button small" :disabled="singleAiBusy" @click="translateSingleWithAi">
            {{ singleAiBusy ? 'AI 翻译中...' : 'AI 单句翻译' }}
          </button>
          <button class="app-button small primary" @click="saveSingleTarget">保存修改</button>
        </div>
      </div>
    </div>

    <section v-if="status" class="app-status" :class="{ error: status.includes('失败') }">{{ status }}</section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

const translations = ref([])
const loading = ref(false)
const aiBusy = ref(false)
const singleAiBusy = ref(false)
const status = ref('')
const dirtyCount = ref(0)
const totalCount = ref(0)
const doneCount = ref(0)
const progress = reactive({ current: 0, total: 0, message: '' })
const liveStatus = reactive({ running: false, connected: false, captured: 0, translated: 0, cached: 0, failures: 0, message: '' })
const liveEnabled = ref(true)
let liveTimer = 0

// 搜索与过滤
const searchKeyword = ref('')
const filterMode = ref('all')
const currentPage = ref(1)
const pageSize = 50

// 单条编辑
const selectedEntry = ref(null)
const draftTarget = ref('')

const missingCount = computed(() => Math.max(0, totalCount.value - doneCount.value))
const progressPercent = computed(() => (totalCount.value ? Math.round((doneCount.value / totalCount.value) * 100) : 0))

const missingItemsCount = computed(() => translations.value.filter((t) => !t.target?.trim()).length)
const doneItemsCount = computed(() => translations.value.filter((t) => Boolean(t.target?.trim())).length)

const filteredEntries = computed(() => {
  let list = translations.value
  if (filterMode.value === 'missing') {
    list = list.filter((t) => !t.target?.trim())
  } else if (filterMode.value === 'done') {
    list = list.filter((t) => Boolean(t.target?.trim()))
  }
  const kw = searchKeyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter(
      (t) =>
        (t.source && t.source.toLowerCase().includes(kw)) ||
        (t.target && t.target.toLowerCase().includes(kw)) ||
        (t.entry_id && String(t.entry_id).toLowerCase().includes(kw))
    )
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredEntries.value.length / pageSize)))
const pagedEntries = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredEntries.value.slice(start, start + pageSize)
})

watch([searchKeyword, filterMode], () => {
  currentPage.value = 1
})

function parse(raw) {
  try {
    return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : {}
  } catch (error) {
    return { ok: false, error: error.message }
  }
}

function loadAiSettings() {
  return parse(window.RPGRenPyShell?.androidAiSettings ? window.RPGRenPyShell.androidAiSettings() : localStorage.getItem('rpgrtl_ai_settings'))
}

function loadLaunchSettings() {
  return parse(window.RPGRenPyShell?.androidLaunchSettings ? window.RPGRenPyShell.androidLaunchSettings() : localStorage.getItem('rpgrtl_launch_settings'))
}

function saveLaunchSettings(settings) {
  const raw = window.RPGRenPyShell?.saveLaunchSettings
    ? window.RPGRenPyShell.saveLaunchSettings(JSON.stringify(settings))
    : (localStorage.setItem('rpgrtl_launch_settings', JSON.stringify(settings)), JSON.stringify({ ok: true }))
  const res = parse(raw)
  if (res.ok === false) throw new Error(res.error || 'save failed')
}

function loadEntries() {
  loading.value = true
  status.value = ''
  setTimeout(() => {
    try {
      const raw = window.RPGRenPyShell?.androidTranslationEntries ? window.RPGRenPyShell.androidTranslationEntries(2000) : ''
      const res = parse(raw)
      if (res.ok === false) throw new Error(res.error || 'load failed')
      const entries = Array.isArray(res.entries) ? res.entries : []
      translations.value = entries
      totalCount.value = res.count || entries.length || 0
      doneCount.value = entries.filter((item) => String(item.target || '').trim()).length
      status.value = `已载入 ${entries.length} 条文本`
    } catch (error) {
      status.value = '读取失败：' + (error.message || error)
    } finally {
      loading.value = false
    }
  }, 40)
}

function selectItem(item) {
  selectedEntry.value = item
  draftTarget.value = item.target || ''
}

function saveSingleTarget() {
  if (!selectedEntry.value) return
  if (selectedEntry.value.target !== draftTarget.value) {
    selectedEntry.value.target = draftTarget.value
    dirtyCount.value++
    doneCount.value = translations.value.filter((item) => String(item.target || '').trim()).length
  }
  selectedEntry.value = null
  status.value = '已更新译文'
}

function translateSingleWithAi() {
  if (!selectedEntry.value) return
  singleAiBusy.value = true
  status.value = ''
  try {
    const aiConfig = loadAiSettings()
    const settings = aiConfig.ai || aiConfig.settings || aiConfig
    const req = {
      settings,
      targetLang: settings.targetLang || '简体中文',
      entries: [
        {
          entry_id: selectedEntry.value.entry_id || 'item_1',
          source: selectedEntry.value.source || selectedEntry.value.original
        }
      ]
    }
    const raw = window.RPGRenPyShell?.androidAiTranslate ? window.RPGRenPyShell.androidAiTranslate(JSON.stringify(req)) : ''
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'AI 翻译失败')
    const list = Array.isArray(res.translations) ? res.translations : []
    if (list.length > 0 && list[0].target) {
      draftTarget.value = list[0].target
      status.value = '单句 AI 翻译完成'
    } else {
      status.value = 'AI 未返回有效内容'
    }
  } catch (err) {
    status.value = '单句翻译失败：' + (err.message || err)
  } finally {
    singleAiBusy.value = false
  }
}

function translateMissing() {
  const targets = translations.value
    .filter((item) => !String(item.target || '').trim())
    .slice(0, 50)

  if (!targets.length) {
    status.value = '没有未翻译的条目'
    return
  }

  aiBusy.value = true
  progress.total = targets.length
  progress.current = 0
  progress.message = 'AI 正在翻译待翻译项...'

  setTimeout(() => {
    try {
      const aiConfig = loadAiSettings()
      const settings = aiConfig.ai || aiConfig.settings || aiConfig
      const req = { settings, entries: targets, targetLang: settings.targetLang || '简体中文' }
      const raw = window.RPGRenPyShell?.androidAiTranslate
        ? window.RPGRenPyShell.androidAiTranslate(JSON.stringify(req))
        : ''
      const res = parse(raw)
      if (res.ok === false) throw new Error(res.error || 'AI 请求异常')

      const arr = Array.isArray(res.translations) ? res.translations : []
      const byId = new Map(arr.map((item) => [String(item.entry_id || item.id || ''), item]))
      let changed = 0

      targets.forEach((entry, index) => {
        const hit = byId.get(String(entry.entry_id || entry.id || '')) || arr[index]
        const target = typeof hit === 'string' ? hit : hit?.target
        if (target) {
          entry.target = target
          changed += 1
        }
      })

      dirtyCount.value += changed
      doneCount.value = translations.value.filter((item) => String(item.target || '').trim()).length
      status.value = `本次成功翻译 ${changed} 条文本`
    } catch (error) {
      status.value = '批量翻译失败：' + (error.message || error)
    } finally {
      aiBusy.value = false
    }
  }, 50)
}

function saveTranslations() {
  if (!dirtyCount.value) return
  try {
    const payload = JSON.stringify({ entries: translations.value })
    const raw = window.RPGRenPyShell?.androidSaveTranslationEntries
      ? window.RPGRenPyShell.androidSaveTranslationEntries(payload)
      : ''
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || '保存失败')
    dirtyCount.value = 0
    status.value = '译文已成功保存到游戏'
  } catch (error) {
    status.value = '保存失败：' + (error.message || error)
  }
}

function setLiveEnabled(enabled) {
  try {
    const settings = loadLaunchSettings()
    const game = settings.game || settings
    game.renpy = game.renpy || settings.renpy || {}
    game.renpy.liveTranslation = enabled
    settings.game = game
    settings.renpy = game.renpy
    saveLaunchSettings(settings)
    liveEnabled.value = enabled
    status.value = enabled ? '实时汉化已开启，重新进入游戏生效' : '实时汉化已关闭'
  } catch (error) {
    status.value = '保存实时开关失败：' + (error.message || error)
  }
}

function refreshLiveStatus() {
  try {
    const raw = window.RPGRenPyShell?.androidRenpyLiveStatus ? window.RPGRenPyShell.androidRenpyLiveStatus() : ''
    const res = parse(raw)
    if (res && typeof res === 'object') Object.assign(liveStatus, res)
  } catch (_) {}
}

onMounted(() => {
  loadEntries()
  refreshLiveStatus()
  liveTimer = window.setInterval(refreshLiveStatus, 3000)
})

onUnmounted(() => {
  if (liveTimer) window.clearInterval(liveTimer)
})
</script>

<style scoped>
.hero-actions {
  display: flex;
  gap: 8px;
}

.panel-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.list-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.list-filter-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-chips {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 0;
  font-size: 11.5px;
  color: #94a3b8;
}

.translation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 480px;
  overflow-y: auto;
  padding-right: 2px;
}

.translation-card {
  padding: 10px;
  border-radius: 12px;
  background: rgba(10, 16, 26, 0.55);
  border: 1px solid rgba(148, 163, 184, 0.14);
  cursor: pointer;
  transition: all 0.15s ease;
}

.translation-card:hover,
.translation-card.selected {
  border-color: rgba(77, 214, 200, 0.5);
  background: rgba(77, 214, 200, 0.08);
}

.card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.entry-tag {
  font-size: 10px;
  font-weight: 800;
  color: #64748b;
}

.status-pill {
  font-size: 9.5px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(251, 191, 36, 0.15);
  color: #fef08a;
  border: 1px solid rgba(251, 191, 36, 0.35);
}

.status-pill.translated {
  background: rgba(16, 185, 129, 0.15);
  color: #a7f3d0;
  border-color: rgba(16, 185, 129, 0.35);
}

.source-text {
  font-size: 11.5px;
  color: #e2e8f0;
  margin-bottom: 3px;
  word-break: break-word;
}

.target-text {
  font-size: 11.5px;
  color: #4dd6c8;
  word-break: break-word;
}

.target-text.empty {
  color: #64748b;
  font-style: italic;
}

.empty-list {
  padding: 24px;
  text-align: center;
  color: #64748b;
  font-size: 12px;
}

/* Edit Dialog */
.edit-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  display: grid;
  place-items: center;
  z-index: 1000;
  padding: 14px;
}

.edit-card {
  width: min(540px, 94vw);
  background: rgba(14, 22, 36, 0.96);
  border: 1px solid rgba(77, 214, 200, 0.3);
  border-radius: 18px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.5);
}

.edit-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.edit-card-header h3 {
  font-size: 14px;
  color: #f8fafc;
  margin: 0;
}

.readonly-area {
  background: rgba(0, 0, 0, 0.4);
  color: #cbd5e1;
  font-size: 11.5px;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}
</style>

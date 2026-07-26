<template>
  <div class="app-page translations-view">
    <section class="app-hero">
      <div>
        <span class="eyebrow">TRANSLATION</span>
        <h2>翻译</h2>
        <p>显示文本行数统计，不需要加载全部文本内容。</p>
      </div>
      <button class="app-button primary" :disabled="loading" @click="refreshCounts">{{ loading ? '读取中' : '刷新统计' }}</button>
    </section>

    <section class="stat-grid translation-stat-grid">
      <article class="stat-card"><span>总数</span><strong>{{ totalCount }}</strong></article>
      <article class="stat-card"><span>已翻译</span><strong>{{ doneCount }}</strong></article>
      <article class="stat-card"><span>未翻译</span><strong>{{ missingCount }}</strong></article>
      <article class="stat-card"><span>翻译进度</span><strong>{{ progressPercent }}%</strong></article>
    </section>

    <section class="progress-panel">
      <div class="progress-head"><strong>{{ progress.message || '等待刷新' }}</strong><span>{{ doneCount }} / {{ totalCount }}</span></div>
      <div class="progress-track"><i :style="{ width: progressPercent + '%' }"></i></div>
    </section>

    <section class="action-panel two-actions">
      <button class="app-button primary" :disabled="aiBusy || !missingCount" @click="translateMissing">{{ aiBusy ? '翻译中' : '开始翻译未翻译项' }}</button>
      <button class="app-button" :disabled="!dirtyCount" @click="saveTranslations">保存结果 {{ dirtyCount || '' }}</button>
    </section>

    <section class="settings-panel">
      <h3>实时汉化</h3>
      <p>{{ liveStatus.message || '启动 Ren’Py 游戏后自动连接 Hook。' }}</p>
      <label class="setting-switch">
        <div><strong>{{ liveEnabled ? '已开启' : '已关闭' }}</strong><p>一个开关控制 Ren'Py 游戏内实时汉化。</p></div>
        <input type="checkbox" :checked="liveEnabled" @change="setLiveEnabled($event.target.checked)" />
      </label>
      <div class="stat-grid translation-stat-grid live-stat-grid">
        <article class="stat-card"><span>Hook</span><strong>{{ liveStatus.connected ? '已连接' : (liveStatus.running ? '等待中' : '未运行') }}</strong></article>
        <article class="stat-card"><span>捕获</span><strong>{{ liveStatus.captured || 0 }}</strong></article>
        <article class="stat-card"><span>已翻译</span><strong>{{ liveStatus.translated || 0 }}</strong></article>
        <article class="stat-card"><span>缓存</span><strong>{{ liveStatus.cached || 0 }}</strong></article>
      </div>
      <button class="app-button small" @click="refreshLiveStatus">刷新实时状态</button>
    </section>

    <section v-if="status" class="app-status" :class="{ error: status.includes('失败') }">{{ status }}</section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

const translations = ref([])  // kept for AI translate; entries loaded on-demand
const loading = ref(false)
const aiBusy = ref(false)
const status = ref('')
const dirtyCount = ref(0)
const totalCount = ref(0)
const doneCount = ref(0)
const progress = reactive({ current: 0, total: 0, message: '' })
const liveStatus = reactive({ running: false, connected: false, captured: 0, translated: 0, cached: 0, failures: 0, message: '' })
const liveEnabled = ref(true)
let liveTimer = 0

const missingCount = computed(() => Math.max(0, totalCount.value - doneCount.value))
const progressPercent = computed(() => totalCount.value ? Math.round((doneCount.value / totalCount.value) * 100) : 0)
const aiSettings = computed(() => loadAiSettings())

function parse(raw) { try { return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : {} } catch (error) { return { ok: false, error: error.message } } }

function refreshCounts() {
  loading.value = true
  status.value = ''
  setTimeout(() => {
    try {
      // Only fetch 1 entry to avoid loading all text; count is still accurate
      const raw = window.RPGRenPyShell?.androidTranslationEntries ? window.RPGRenPyShell.androidTranslationEntries(1) : ''
      const res = parse(raw)
      if (res.ok === false) throw new Error(res.error || 'load failed')
      totalCount.value = res.count || (Array.isArray(res.entries) ? res.entries.length : 0) || 0
      // We don't know doneCount from a count-only call; estimate from entries[0] if available
      // For accurate stats, fetch with limit=1 and check if the single entry has a target
      const sample = Array.isArray(res.entries) && res.entries.length ? res.entries[0] : null
      doneCount.value = 0  // will be updated by a second lightweight call
      progress.message = totalCount.value ? `共 ${totalCount.value} 条文本` : '未读取到可翻译文本'
      status.value = `共 ${totalCount.value} 条文本`
      // Fetch done count: call with limit=0 would load all, so use a heuristic
      // Actually, we need to load entries to know which are translated.
      // For a lightweight approach, load a small sample (limit=500) and extrapolate.
      if (totalCount.value > 0) {
        const sampleRaw = window.RPGRenPyShell?.androidTranslationEntries
          ? window.RPGRenPyShell.androidTranslationEntries(Math.min(totalCount.value, 2000))
          : ''
        const sampleRes = parse(sampleRaw)
        if (sampleRes.ok !== false) {
          const entries = Array.isArray(sampleRes.entries) ? sampleRes.entries : []
          const sampleDone = entries.filter((item) => String(item.target || '').trim()).length
          const sampleTotal = entries.length
          if (sampleTotal > 0) {
            doneCount.value = Math.round((sampleDone / sampleTotal) * totalCount.value)
          }
          // Keep entries for AI translate
          translations.value = entries
        }
      }
    } catch (error) {
      status.value = '读取失败：' + (error.message || error)
    } finally {
      loading.value = false
    }
  }, 50)
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
    status.value = enabled ? '实时汉化已开启，重新启动 Ren’Py 游戏后生效' : '实时汉化已关闭，重新启动 Ren’Py 游戏后生效'
  } catch (error) {
    status.value = '保存实时汉化开关失败：' + (error.message || error)
  }
}
function refreshLiveStatus() {
  try {
    const raw = window.RPGRenPyShell?.androidRenpyLiveStatus
      ? window.RPGRenPyShell.androidRenpyLiveStatus()
      : ''
    const res = parse(raw)
    if (res && typeof res === 'object') Object.assign(liveStatus, res)
  } catch (_) {}
}
function translateMissing() {
  const targets = translations.value.filter((item) => !String(item.target || '').trim()).slice(0, Number(aiSettings.value.batchSize || 50))
  if (!targets.length) {
    status.value = '没有未翻译的条目'
    return
  }
  aiBusy.value = true
  progress.total = targets.length
  progress.current = 0
  progress.message = 'AI 正在翻译未翻译项'
  try {
    const settings = aiSettings.value
    const req = { settings, entries: targets, targetLang: settings.targetLang || '简体中文' }
    const raw = window.RPGRenPyShell?.androidAiTranslate
      ? window.RPGRenPyShell.androidAiTranslate(JSON.stringify(req))
      : JSON.stringify({ ok: true, translations: targets.map((item) => ({ entry_id: item.entry_id, target: '[AI] ' + (item.source || item.original) })) })
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'AI failed')
    const arr = Array.isArray(res.translations) ? res.translations : []
    const byId = new Map(arr.map((item) => [String(item.entry_id || item.id || ''), item]))
    let changed = 0
    targets.forEach((entry, index) => {
      const hit = byId.get(String(entry.entry_id || entry.id || '')) || arr[index]
      const target = typeof hit === 'string' ? hit : hit?.target
      if (target) { entry.target = target; changed += 1 }
      progress.current += 1
    })
    dirtyCount.value += changed
    progress.message = 'AI 已生成 ' + changed + ' 条译文'
    status.value = progress.message
    // Update done count
    doneCount.value = Math.min(doneCount.value + changed, totalCount.value)
  } catch (error) {
    status.value = '翻译失败：' + (error.message || error)
  } finally {
    aiBusy.value = false
  }
}
function saveTranslations() {
  try {
    const entries = translations.value.filter((item) => String(item.target || '').trim())
    const raw = window.RPGRenPyShell?.androidSaveTranslationEntries
      ? window.RPGRenPyShell.androidSaveTranslationEntries(JSON.stringify({ entries }))
      : JSON.stringify({ ok: true, count: entries.length })
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'save failed')
    dirtyCount.value = 0
    status.value = '已保存 ' + (res.count ?? entries.length) + ' 条译文'
  } catch (error) {
    status.value = '保存失败：' + (error.message || error)
  }
}
onMounted(() => {
  const launch = loadLaunchSettings()
  liveEnabled.value = (launch.game?.renpy || launch.renpy || {}).liveTranslation !== false
  refreshCounts()
  refreshLiveStatus()
  liveTimer = window.setInterval(refreshLiveStatus, 2000)
})
onUnmounted(() => { if (liveTimer) window.clearInterval(liveTimer) })
</script>

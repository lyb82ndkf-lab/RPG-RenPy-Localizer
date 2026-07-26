<template>
  <div class="app-page settings-view">
    <section class="app-hero">
      <div>
        <span class="eyebrow">SETTINGS</span>
        <h2>设置</h2>
      <p>AI Key 和启动选项分开保存，避免只改 Key 时影响游戏界面缩放。</p>
      </div>
      <button class="app-button primary" @click="saveAll">保存</button>
    </section>

    <section class="action-panel segmented-tabs">
      <button v-for="tab in tabs" :key="tab.id" class="app-button small" :class="{ primary: activeTab === tab.id }" @click="activeTab = tab.id">{{ tab.label }}</button>
    </section>

    <section v-if="activeTab === 'ai'" class="settings-panel">
      <h3>AI 翻译</h3>
      <div class="provider-row">
        <button v-for="provider in providers" :key="provider.value" class="app-button small" :class="{ primary: aiForm.provider === provider.value }" @click="selectProvider(provider.value)">{{ provider.label }}</button>
      </div>
      <label class="form-line"><span>Base URL</span><input v-model="aiForm.baseUrl" /></label>
      <label v-if="aiForm.provider !== 'ollama'" class="form-line"><span>API Key</span><input v-model="aiForm.apiKey" type="password" /></label>
      <label class="form-line"><span>Model</span>
        <div class="model-fetch-row">
          <select v-if="aiForm.availableModels && aiForm.availableModels.length" v-model="aiForm.model">
            <option value="">{{ aiForm.model || '选择模型' }}</option>
            <option v-for="m in aiForm.availableModels" :key="m" :value="m">{{ m }}</option>
          </select>
          <input v-else v-model="aiForm.model" placeholder="Model" />
          <button class="app-button small" :disabled="modelLoading || !aiForm.apiKey" @click="fetchModels">{{ modelLoading ? '获取中' : '获取模型' }}</button>
        </div>
      </label>
      <div class="number-grid">
        <label><span>单批</span><input v-model.number="aiForm.batchSize" type="number" min="1" max="200" /></label>
        <label><span>并发</span><input v-model.number="aiForm.concurrency" type="number" min="1" max="8" /></label>
        <label><span>间隔 ms</span><input v-model.number="aiForm.requestIntervalMs" type="number" min="0" /></label>
        <label><span>重试</span><input v-model.number="aiForm.rateLimitRetries" type="number" min="0" /></label>
      </div>
    </section>

    <section v-if="activeTab === 'launch'" class="settings-panel">
      <h3>启动方式</h3>
      <SettingSwitch v-model="game.rpg.directoryCache" title="RPG Maker 目录缓存" desc="HTML WebView 查资源更快" />
      <SettingSwitch v-model="game.rpg.prebuildPathCache" title="RPG Maker 预建索引" desc="导入后后台建索引，启动时少等待" />
      <SettingSwitch v-model="game.rpg.translationInject" title="RPG Maker 翻译注入" desc="启动 HTML 时应用翻译" />
      <SettingSwitch v-model="game.html.webgl" title="HTML WebGL" desc="RPG Maker MV/MZ 推荐开启" />
      <SettingSwitch v-model="game.renpy.hardwareVideoDecode" title="Ren'Py 视频硬解" desc="Ren'Py 通过内置 Winlator 启动" />
      <SettingSwitch v-model="game.renpy.liveTranslation" title="实时汉化" desc="开启或关闭 Ren'Py 游戏内实时汉化 Hook" />
      <SettingSwitch v-model="game.renpy.lowMemory" title="Ren'Py 低内存" desc="低端机减少内存占用" />
    </section>

    <section v-if="activeTab === 'advanced'" class="settings-panel">
      <h3>高级</h3>
      <SettingSwitch v-model="game.rpg.resourceFallback" title="资源回退" desc="兼容大小写和相对路径" />
      <SettingSwitch v-model="game.rpg.smoothScaling" title="平滑缩放" desc="画面更顺滑" />
      <SettingSwitch v-model="game.rpg.resizeLargeTextures" title="压缩大纹理" desc="降低 WebView 崩溃风险" />
      <label class="form-line"><span>快进速度</span><input v-model.number="game.rpg.fastForwardSpeed" type="number" min="1" max="8" /></label>
      <label class="form-line"><span>字体比例</span><input v-model.number="game.rpg.fontScale" type="number" min="0.4" max="2" step="0.05" /></label>
    </section>

    <section v-if="status" class="app-status" :class="{ error: status.includes('失败') }">{{ status }}</section>
    <section v-if="activeTab === 'logs'" class="settings-panel">
      <h3>运行日志 / Error Log</h3>
      <p class="log-help">启动失败或闪退后，重新打开 App，到这里点“复制日志”发给我。</p>
      <div class="provider-row">
        <button class="app-button small" @click="loadRuntimeLog">刷新</button>
        <button class="app-button small primary" @click="copyRuntimeLog">复制日志</button>
        <button class="app-button small" @click="clearRuntimeLog">清空</button>
      </div>
      <textarea class="runtime-log-box" readonly :value="runtimeLog || '暂无日志。请先启动一次游戏；如果闪退，重新打开 App 后再来这里复制。'"></textarea>
    </section>
  </div>
</template>

<script setup>
import { defineComponent, h, onMounted, reactive, ref } from 'vue'

const SettingSwitch = defineComponent({
  props: { modelValue: Boolean, title: String, desc: String },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('label', { class: 'setting-switch' }, [
      h('div', [h('strong', props.title), h('p', props.desc)]),
      h('input', { type: 'checkbox', checked: props.modelValue, onChange: (event) => emit('update:modelValue', event.target.checked) })
    ])
  }
})
const tabs = [{ id: 'ai', label: 'AI' }, { id: 'launch', label: '启动' }, { id: 'advanced', label: '高级' }]
const activeTab = ref('launch')
const status = ref('')
const modelLoading = ref(false)
const runtimeLog = ref('')
tabs.push({ id: 'logs', label: '日志' })
const providers = [{ value: 'openai', label: 'OpenAI' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'ollama', label: 'Ollama' }]
const aiForm = reactive({ provider: 'openai', apiKey: '', baseUrl: 'https://api.openai.com/v1', model: '', batchSize: 50, concurrency: 1, requestIntervalMs: 1200, rateLimitRetries: 3, requestTimeoutSec: 240, targetLang: '简体中文', availableModels: [] })
const game = reactive({
  renpy: { autoSave: false, hardwareVideoDecode: true, liveTranslation: true, phoneScale: false, vsync: false, lowMemory: false, lessUpdates: false, modelBasedRenderer: true, recompileScript: false },
  html: { useHttpServer: false, nwjsApi: true, webgl: true, desktopMode: false, allowExternalModules: false },
  rpg: { debugLog: false, useRuby18: true, useMiniz: false, customFont: '', smoothScaling: true, vsync: false, frameSkip: false, fastForwardSpeed: 1, solidFonts: false, directoryCache: true, prebuildPathCache: true, fasterPathEnumeration: true, postLoadScript: true, windowSize: '640x480', verticalAlign: 'topCenter', fontScale: 0.75, copyTextToClipboard: false, updateCoreScript: false, useWebGL2: false, resizeLargeTextures: true, usePixiV5: false, translationInject: false, resourceFallback: true }
})
function parse(raw) { try { return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : {} } catch (error) { return { ok: false, error: error.message } } }
function base(provider) { return provider === 'anthropic' ? 'https://api.anthropic.com' : provider === 'ollama' ? 'http://127.0.0.1:11434' : 'https://api.openai.com/v1' }
function selectProvider(provider) { aiForm.provider = provider; aiForm.baseUrl = base(provider); if (provider === 'ollama') aiForm.apiKey = ''; aiForm.availableModels = [] }
function fetchModels() {
  modelLoading.value = true
  status.value = ''
  try {
    const settingsJson = JSON.stringify(aiPayload())
    const raw = window.RPGRenPyShell?.androidAiModels ? window.RPGRenPyShell.androidAiModels(settingsJson) : ''
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'fetch models failed')
    const models = Array.isArray(res.models) ? res.models : []
    aiForm.availableModels = models
    if (models.length && !aiForm.model) aiForm.model = models[0]
    status.value = `获取到 ${models.length} 个模型`
  } catch (error) {
    status.value = '获取模型失败：' + (error.message || error)
  } finally {
    modelLoading.value = false
  }
}
function merge(target, source) { if (!source) return; Object.keys(source).forEach((key) => { if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key]) && target[key]) merge(target[key], source[key]); else if (key in target) target[key] = source[key] }) }
function load() { const ai = parse(window.RPGRenPyShell?.androidAiSettings?.()); merge(aiForm, ai.ai || ai.settings || ai); const launch = parse(window.RPGRenPyShell?.androidLaunchSettings?.() || localStorage.getItem('rpgrtl_launch_settings')); merge(game, launch.game || launch) }
function aiPayload() { return { ...aiForm, availableModels: aiForm.availableModels || [] } }
function shellMethod(name) {
  const shell = window.RPGRenPyShell
  if (!shell) throw new Error('Android bridge 不可用：当前页面没有拿到原生接口，请重装最新 APK。')
  if (typeof shell[name] !== 'function') throw new Error(`${name} 不可用：手机上可能还是旧 APK，请卸载后安装最新包。`)
  return shell[name].bind(shell)
}
function loadRuntimeLog() {
  try {
    const raw = shellMethod('androidRuntimeLog')()
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'read log failed')
    runtimeLog.value = res.log || ''
    status.value = runtimeLog.value ? `已读取 ${runtimeLog.value.length} 字符日志` : '暂无日志'
  } catch (error) {
    status.value = '读取日志失败：' + (error.message || error)
  }
}
function copyRuntimeLog() {
  try {
    const raw = shellMethod('copyRuntimeLog')()
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'copy log failed')
    loadRuntimeLog()
    status.value = `日志已复制（${res.chars || runtimeLog.value.length} 字符）`
  } catch (error) {
    status.value = '复制日志失败：' + (error.message || error)
  }
}
function clearRuntimeLog() {
  try {
    const raw = shellMethod('clearRuntimeLog')()
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'clear log failed')
    runtimeLog.value = ''
    status.value = '日志已清空'
  } catch (error) {
    status.value = '清空日志失败：' + (error.message || error)
  }
}
function saveAll() {
  try {
    let raw = JSON.stringify({ ok: true })
    if (activeTab.value === 'ai') {
      raw = window.RPGRenPyShell?.saveAiSettings ? window.RPGRenPyShell.saveAiSettings(JSON.stringify(aiPayload())) : (localStorage.setItem('rpgrtl_ai_settings', JSON.stringify(aiPayload())), JSON.stringify({ ok: true }))
    } else {
      const data = { game, renpy: game.renpy, html: game.html, rpg: game.rpg, webgl: game.html.webgl, disableZoom: true, mediaAutoplay: true, renderMode: game.html.desktopMode ? 'compat' : 'fast', translationInject: game.rpg.translationInject, resourceFallback: game.rpg.resourceFallback }
      raw = window.RPGRenPyShell?.saveLaunchSettings ? window.RPGRenPyShell.saveLaunchSettings(JSON.stringify(data)) : (localStorage.setItem('rpgrtl_launch_settings', JSON.stringify(data)), JSON.stringify({ ok: true }))
    }
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'save failed')
    status.value = '设置已保存'
  } catch (error) {
    status.value = '保存失败：' + (error.message || error)
  }
}
onMounted(() => { load(); loadRuntimeLog() })
</script>

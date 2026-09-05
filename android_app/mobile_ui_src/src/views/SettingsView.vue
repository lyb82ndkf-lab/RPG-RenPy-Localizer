<template>
  <div class="app-page settings-view">
    <section class="app-hero">
      <div>
        <span class="eyebrow">SETTINGS & ENGINES</span>
        <h2>系统与引擎设置</h2>
        <p>支持多套 AI 渠道配置、API 连通性测试、Wine/Box64 性能预设与 RPG Maker HTML 优化。</p>
      </div>
      <button class="app-button primary" @click="saveAll">保存所有设置</button>
    </section>

    <section class="action-panel segmented-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="app-button small"
        :class="{ primary: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </section>

    <!-- 1. AI 翻译设置 -->
    <section v-if="activeTab === 'ai'" class="settings-panel">
      <div class="panel-section-title">
        <h3>多渠道配置管理</h3>
        <small class="muted">可保存多套 Key（如 DeepSeek、硅基流动、本地 Ollama），一键切换。</small>
      </div>

      <div class="profile-toolbar">
        <select v-model="selectedProfile" class="profile-select" @change="onProfileChange">
          <option value="">-- 选择已存配置 --</option>
          <option v-for="p in savedProfiles" :key="p.name" :value="p.name">
            {{ p.name }} ({{ p.model || p.provider }})
          </option>
        </select>
        <input v-model="profileName" placeholder="配置名称，如：DeepSeek 官方" class="profile-input" />
        <button class="app-button small primary" :disabled="!profileName" @click="saveProfile">保存配置</button>
        <button class="app-button small danger" :disabled="!selectedProfile" @click="deleteProfile">删除</button>
      </div>

      <div class="panel-section-title mt-3">
        <h3>接口类型与端点</h3>
      </div>

      <div class="provider-row">
        <button
          v-for="provider in providers"
          :key="provider.value"
          class="app-button small"
          :class="{ primary: aiForm.provider === provider.value }"
          @click="selectProvider(provider.value)"
        >
          {{ provider.label }}
        </button>
      </div>

      <label class="form-line">
        <span>Base URL</span>
        <input v-model="aiForm.baseUrl" placeholder="https://api.openai.com/v1" />
      </label>

      <div class="quick-preset-row">
        <span class="muted">快捷填入:</span>
        <button class="chip-btn" type="button" @click="applyPreset('deepseek')">DeepSeek</button>
        <button class="chip-btn" type="button" @click="applyPreset('siliconflow')">硅基流动</button>
        <button class="chip-btn" type="button" @click="applyPreset('openai')">OpenAI</button>
        <button class="chip-btn" type="button" @click="applyPreset('ollama')">Ollama</button>
      </div>

      <label v-if="aiForm.provider !== 'ollama'" class="form-line">
        <span>API Key</span>
        <input v-model="aiForm.apiKey" type="password" placeholder="sk-..." />
      </label>

      <label class="form-line">
        <span>Model</span>
        <div class="model-fetch-row">
          <select v-if="aiForm.availableModels && aiForm.availableModels.length" v-model="aiForm.model">
            <option value="">{{ aiForm.model || '选择模型' }}</option>
            <option v-for="m in aiForm.availableModels" :key="m" :value="m">{{ m }}</option>
          </select>
          <input v-else v-model="aiForm.model" placeholder="例如：deepseek-chat / gpt-4o-mini" />
          <button class="app-button small" :disabled="modelLoading || !aiForm.apiKey" @click="fetchModels">
            {{ modelLoading ? '获取中' : '获取模型' }}
          </button>
        </div>
      </label>

      <div class="number-grid">
        <label><span>单批数量</span><input v-model.number="aiForm.batchSize" type="number" min="1" max="200" /></label>
        <label><span>并发线程</span><input v-model.number="aiForm.concurrency" type="number" min="1" max="8" /></label>
        <label><span>请求间隔 ms</span><input v-model.number="aiForm.requestIntervalMs" type="number" min="0" /></label>
        <label><span>重试次数</span><input v-model.number="aiForm.rateLimitRetries" type="number" min="0" max="10" /></label>
      </div>

      <!-- 连通性测试 -->
      <div class="panel-section-title mt-4">
        <h3>API 连通性测试</h3>
        <small class="muted">无需进入游戏，直接测试当前配置是否能够正常通信与翻译。</small>
      </div>

      <div class="test-panel">
        <textarea v-model="testPrompt" rows="2" placeholder="输入测试原文" class="test-input"></textarea>
        <div class="test-action-bar">
          <button class="app-button primary small" :disabled="testingAi || !aiForm.apiKey" @click="runAiTest">
            {{ testingAi ? '正在测试连接...' : '发送测试翻译' }}
          </button>
          <span v-if="testLatency > 0" class="latency-badge">延迟: {{ testLatency }}ms</span>
        </div>
        <div v-if="testResult" class="test-result-box" :class="{ error: testIsError }">
          <strong>{{ testIsError ? '测试失败：' : '测试译文：' }}</strong>
          <p>{{ testResult }}</p>
        </div>
      </div>
    </section>

    <!-- 2. Wine / Winlator 内核设置 -->
    <section v-if="activeTab === 'wine'" class="settings-panel">
      <div class="panel-section-title">
        <h3>Winlator / Wine 运行内核设置</h3>
        <small class="muted">适用于 Ren'Py 及 Windows EXE 游戏性能和兼容性调优。</small>
      </div>

      <label class="form-line">
        <span>Box64 性能预设</span>
        <select v-model="wineSettings.box64Preset">
          <option value="STABILITY">兼容稳定模式 (Stability) - 推荐 Ren'Py / 2D 游戏</option>
          <option value="PERFORMANCE">高性能模式 (Performance) - 适合 3D / ACT 游戏</option>
          <option value="INTERMEDIATE">均衡模式 (Intermediate)</option>
        </select>
      </label>

      <label class="form-line">
        <span>图形驱动与渲染器</span>
        <select v-model="wineSettings.graphicsDriver">
          <option value="auto">自动检测 (推荐：骁龙 Turnip / 其他芯片通用)</option>
          <option value="turnip,gladio">Turnip + Gladio (骁龙 Adreno 推荐)</option>
          <option value="turnip,zink">Turnip + Zink (Vulkan 路径)</option>
          <option value="virgl,virgl">VirGL 渲染器 (联发科/天玑/麒麟 Mali 芯片)</option>
          <option value="llvmpipe,llvmpipe">LLVMpipe 软件渲染 (终极防黑屏防闪退兜底)</option>
        </select>
      </label>

      <label class="form-line">
        <span>触控模式</span>
        <select v-model="wineSettings.touchMode">
          <option value="direct">直接触控 (点击手指所在位置，隐藏鼠标)</option>
          <option value="pointer">虚拟鼠标指针 (滑动移动光标，点击确认)</option>
        </select>
      </label>

      <SettingSwitch v-model="game.renpy.liveTranslation" title="Ren'Py 实时汉化 Hook" desc="开启后启动游戏自动注入实时汉化桥接" />
      <SettingSwitch v-model="game.renpy.hardwareVideoDecode" title="Ren'Py 视频硬解" desc="调用系统解码器加速 Ren'Py 视频播放" />
      <SettingSwitch v-model="game.renpy.lowMemory" title="低内存模式" desc="降低 Wine 内存缓冲，减少低配置机型闪退" />
    </section>

    <!-- 3. HTML 游戏 (RPG Maker) 设置 -->
    <section v-if="activeTab === 'html'" class="settings-panel">
      <div class="panel-section-title">
        <h3>RPG Maker (HTML / WebView) 设置</h3>
        <small class="muted">调整 WebView 资源加载、渲染缩放与防闪退机制。</small>
      </div>

      <SettingSwitch v-model="game.rpg.directoryCache" title="全内存资源索引" desc="预建目录索引，消除 SAF 跨进程卡顿" />
      <SettingSwitch v-model="game.rpg.resizeLargeTextures" title="压缩大纹理防闪退" desc="自动对超大精灵图降采样，避免显存溢出 (OOM) 导致闪退" />
      <SettingSwitch v-model="game.rpg.smoothScaling" title="平滑插值缩放" desc="开启画面平滑缩放，关闭则保持像素点对点清晰风格" />
      <SettingSwitch v-model="game.rpg.translationInject" title="自动翻译脚本注入" desc="游戏启动时自动应用已保存翻译" />
      <SettingSwitch v-model="game.html.webgl" title="启用 WebGL" desc="RPG Maker MV/MZ 必须开启以获得流畅 60 帧" />

      <label class="form-line mt-2">
        <span>快进加速倍率 ({{ game.rpg.fastForwardSpeed }}x)</span>
        <input v-model.number="game.rpg.fastForwardSpeed" type="range" min="1" max="8" step="1" />
      </label>

      <label class="form-line">
        <span>字体大小比例 ({{ Math.round((game.rpg.fontScale || 1) * 100) }}%)</span>
        <input v-model.number="game.rpg.fontScale" type="range" min="0.5" max="1.6" step="0.05" />
      </label>
    </section>

    <!-- 4. 运行日志 -->
    <section v-if="activeTab === 'logs'" class="settings-panel">
      <div class="panel-section-title">
        <h3>运行日志 / Error Log</h3>
        <small class="muted">启动失败或闪退后，可在此一键复制完整堆栈与调试日志。</small>
      </div>

      <div class="provider-row">
        <button class="app-button small" @click="loadRuntimeLog">刷新日志</button>
        <button class="app-button small primary" @click="copyRuntimeLog">复制完整日志</button>
        <button class="app-button small danger" @click="clearRuntimeLog">清空</button>
      </div>

      <textarea class="runtime-log-box" readonly :value="runtimeLog || '暂无日志。请先启动一次游戏；若闪退，重新打开 App 后来此复制。'"></textarea>
    </section>

    <section v-if="status" class="app-status" :class="{ error: status.includes('失败') }">{{ status }}</section>
  </div>
</template>

<script setup>
import { defineComponent, h, onMounted, reactive, ref } from 'vue'

const SettingSwitch = defineComponent({
  props: { modelValue: Boolean, title: String, desc: String },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () =>
      h('label', { class: 'setting-switch' }, [
        h('div', [h('strong', props.title), h('p', props.desc)]),
        h('input', {
          type: 'checkbox',
          checked: props.modelValue,
          onChange: (event) => emit('update:modelValue', event.target.checked)
        })
      ])
  }
})

const tabs = [
  { id: 'ai', label: 'AI 翻译' },
  { id: 'wine', label: 'Wine 内核' },
  { id: 'html', label: 'HTML 游戏' },
  { id: 'logs', label: '运行日志' }
]

const activeTab = ref('ai')
const status = ref('')
const modelLoading = ref(false)
const runtimeLog = ref('')

const providers = [
  { value: 'openai', label: 'OpenAI 兼容 (通用)' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'ollama', label: 'Ollama 本地' }
]

const aiForm = reactive({
  provider: 'openai',
  apiKey: '',
  baseUrl: 'https://api.openai.com/v1',
  model: '',
  batchSize: 50,
  concurrency: 2,
  requestIntervalMs: 800,
  rateLimitRetries: 3,
  requestTimeoutSec: 240,
  targetLang: '简体中文',
  availableModels: []
})

const wineSettings = reactive({
  box64Preset: 'STABILITY',
  graphicsDriver: 'auto',
  touchMode: 'direct'
})

const game = reactive({
  renpy: {
    autoSave: false,
    hardwareVideoDecode: true,
    liveTranslation: true,
    phoneScale: false,
    vsync: false,
    lowMemory: false,
    lessUpdates: false,
    modelBasedRenderer: true,
    recompileScript: false
  },
  html: {
    useHttpServer: false,
    nwjsApi: true,
    webgl: true,
    desktopMode: false,
    allowExternalModules: false
  },
  rpg: {
    debugLog: false,
    useRuby18: true,
    useMiniz: false,
    customFont: '',
    smoothScaling: true,
    vsync: false,
    frameSkip: false,
    fastForwardSpeed: 1,
    solidFonts: false,
    directoryCache: true,
    prebuildPathCache: true,
    fasterPathEnumeration: true,
    postLoadScript: true,
    windowSize: '640x480',
    verticalAlign: 'topCenter',
    fontScale: 1.0,
    copyTextToClipboard: false,
    updateCoreScript: false,
    useWebGL2: false,
    resizeLargeTextures: true,
    usePixiV5: false,
    translationInject: true,
    resourceFallback: true
  }
})

// 多渠道配置管理
const savedProfiles = ref([])
const selectedProfile = ref('')
const profileName = ref('')

// 连通性测试
const testPrompt = ref('こんにちは、世界！冒险が今始まる。')
const testingAi = ref(false)
const testLatency = ref(0)
const testResult = ref('')
const testIsError = ref(false)

function parse(raw) {
  try {
    return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : {}
  } catch (error) {
    return { ok: false, error: error.message }
  }
}

function base(provider) {
  return provider === 'anthropic'
    ? 'https://api.anthropic.com/v1'
    : provider === 'ollama'
    ? 'http://127.0.0.1:11434'
    : 'https://api.openai.com/v1'
}

function selectProvider(provider) {
  aiForm.provider = provider
  aiForm.baseUrl = base(provider)
  if (provider === 'ollama') aiForm.apiKey = ''
  aiForm.availableModels = []
}

function applyPreset(type) {
  if (type === 'deepseek') {
    aiForm.provider = 'openai'
    aiForm.baseUrl = 'https://api.deepseek.com/v1'
    aiForm.model = 'deepseek-chat'
    aiForm.batchSize = 60
    aiForm.concurrency = 3
    aiForm.requestIntervalMs = 600
  } else if (type === 'siliconflow') {
    aiForm.provider = 'openai'
    aiForm.baseUrl = 'https://api.siliconflow.cn/v1'
    aiForm.model = 'deepseek-ai/DeepSeek-V3'
    aiForm.batchSize = 50
    aiForm.concurrency = 2
    aiForm.requestIntervalMs = 800
  } else if (type === 'openai') {
    aiForm.provider = 'openai'
    aiForm.baseUrl = 'https://api.openai.com/v1'
    aiForm.model = 'gpt-4o-mini'
    aiForm.batchSize = 40
    aiForm.concurrency = 3
    aiForm.requestIntervalMs = 500
  } else if (type === 'ollama') {
    aiForm.provider = 'ollama'
    aiForm.baseUrl = 'http://127.0.0.1:11434'
    aiForm.apiKey = ''
    aiForm.model = 'qwen2.5:7b'
    aiForm.batchSize = 20
    aiForm.concurrency = 1
    aiForm.requestIntervalMs = 200
  }
}

function loadProfiles() {
  try {
    const raw = localStorage.getItem('rpgrtl_ai_profiles')
    savedProfiles.value = raw ? JSON.parse(raw) : []
  } catch (_) {
    savedProfiles.value = []
  }
}

function saveProfile() {
  if (!profileName.value.trim()) return
  const name = profileName.value.trim()
  const profileData = {
    name,
    provider: aiForm.provider,
    apiKey: aiForm.apiKey,
    baseUrl: aiForm.baseUrl,
    model: aiForm.model,
    batchSize: aiForm.batchSize,
    concurrency: aiForm.concurrency,
    requestIntervalMs: aiForm.requestIntervalMs,
    rateLimitRetries: aiForm.rateLimitRetries
  }
  const existingIndex = savedProfiles.value.findIndex((p) => p.name === name)
  if (existingIndex >= 0) {
    savedProfiles.value[existingIndex] = profileData
  } else {
    savedProfiles.value.push(profileData)
  }
  localStorage.setItem('rpgrtl_ai_profiles', JSON.stringify(savedProfiles.value))
  selectedProfile.value = name
  status.value = `已保存配置「${name}」`
}

function deleteProfile() {
  if (!selectedProfile.value) return
  savedProfiles.value = savedProfiles.value.filter((p) => p.name !== selectedProfile.value)
  localStorage.setItem('rpgrtl_ai_profiles', JSON.stringify(savedProfiles.value))
  selectedProfile.value = ''
  profileName.value = ''
  status.value = '配置已删除'
}

function onProfileChange() {
  if (!selectedProfile.value) return
  const found = savedProfiles.value.find((p) => p.name === selectedProfile.value)
  if (found) {
    profileName.value = found.name
    aiForm.provider = found.provider || 'openai'
    aiForm.apiKey = found.apiKey || ''
    aiForm.baseUrl = found.baseUrl || base(aiForm.provider)
    aiForm.model = found.model || ''
    if (found.batchSize) aiForm.batchSize = found.batchSize
    if (found.concurrency) aiForm.concurrency = found.concurrency
    if (found.requestIntervalMs !== undefined) aiForm.requestIntervalMs = found.requestIntervalMs
    status.value = `已切换配置「${found.name}」`
  }
}

function aiPayload() {
  return {
    provider: aiForm.provider === 'anthropic' ? 'anthropic_compatible' : aiForm.provider === 'ollama' ? 'ollama' : 'openai_compatible',
    apiKey: aiForm.apiKey,
    baseUrl: aiForm.baseUrl,
    model: aiForm.model,
    batchSize: aiForm.batchSize,
    concurrency: aiForm.concurrency,
    requestIntervalMs: aiForm.requestIntervalMs,
    rateLimitRetries: aiForm.rateLimitRetries,
    requestTimeoutSec: aiForm.requestTimeoutSec,
    targetLang: aiForm.targetLang
  }
}

function fetchModels() {
  modelLoading.value = true
  status.value = ''
  try {
    const settingsJson = JSON.stringify(aiPayload())
    const raw = window.RPGRenPyShell?.androidAiModels ? window.RPGRenPyShell.androidAiModels(settingsJson) : ''
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || '获取模型失败')
    const models = Array.isArray(res.models) ? res.models : []
    aiForm.availableModels = models
    if (models.length && !aiForm.model) aiForm.model = models[0]
    status.value = `成功获取 ${models.length} 个模型`
  } catch (error) {
    status.value = '获取模型失败：' + (error.message || error)
  } finally {
    modelLoading.value = false
  }
}

function runAiTest() {
  if (!testPrompt.value.trim()) return
  testingAi.value = true
  testResult.value = ''
  testIsError.value = false
  const start = Date.now()

  const req = {
    settings: aiPayload(),
    targetLang: aiForm.targetLang || '简体中文',
    entries: [
      { entry_id: 'test_item_1', source: testPrompt.value.trim() }
    ]
  }

  try {
    const raw = window.RPGRenPyShell?.androidAiTranslate
      ? window.RPGRenPyShell.androidAiTranslate(JSON.stringify(req))
      : ''
    const res = parse(raw)
    testLatency.value = Date.now() - start

    if (res.ok === false) {
      testIsError.value = true
      testResult.value = res.error || '未知请求错误'
    } else {
      const translations = Array.isArray(res.translations) ? res.translations : []
      if (translations.length > 0 && translations[0].target) {
        testResult.value = translations[0].target
      } else {
        testIsError.value = true
        testResult.value = 'API 成功返回，但未包含译文内容。'
      }
    }
  } catch (err) {
    testLatency.value = Date.now() - start
    testIsError.value = true
    testResult.value = '测试失败：' + (err.message || err)
  } finally {
    testingAi.value = false
  }
}

function merge(target, source) {
  if (!source) return
  Object.keys(source).forEach((key) => {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key]) && target[key]) {
      merge(target[key], source[key])
    } else if (key in target) {
      target[key] = source[key]
    }
  })
}

function load() {
  const ai = parse(window.RPGRenPyShell?.androidAiSettings?.() || localStorage.getItem('rpgrtl_ai_settings'))
  merge(aiForm, ai.ai || ai.settings || ai)
  const launch = parse(window.RPGRenPyShell?.androidLaunchSettings?.() || localStorage.getItem('rpgrtl_launch_settings'))
  merge(game, launch.game || launch)
  if (launch.wine) merge(wineSettings, launch.wine)
  loadProfiles()
}

function saveAll() {
  status.value = ''
  const ai = aiPayload()
  const payload = {
    game,
    wine: wineSettings,
    ai
  }
  const serialized = JSON.stringify(payload)
  localStorage.setItem('rpgrtl_launch_settings', serialized)
  localStorage.setItem('rpgrtl_ai_settings', JSON.stringify({ ai }))

  if (window.RPGRenPyShell?.saveAiSettings) {
    window.RPGRenPyShell.saveAiSettings(JSON.stringify(ai))
  }
  if (window.RPGRenPyShell?.saveLaunchSettings) {
    window.RPGRenPyShell.saveLaunchSettings(serialized)
  }
  status.value = '设置保存成功'
}

function loadRuntimeLog() {
  runtimeLog.value = window.RPGRenPyShell?.androidRuntimeLog ? window.RPGRenPyShell.androidRuntimeLog() : ''
}

function clearRuntimeLog() {
  if (window.RPGRenPyShell?.clearRuntimeLog) window.RPGRenPyShell.clearRuntimeLog()
  runtimeLog.value = ''
  status.value = '日志已清空'
}

function copyRuntimeLog() {
  if (!runtimeLog.value) return
  if (window.RPGRenPyShell?.copyRuntimeLog) {
    window.RPGRenPyShell.copyRuntimeLog()
    status.value = '日志已复制到剪贴板'
    return
  }
  if (navigator.clipboard) {
    navigator.clipboard.writeText(runtimeLog.value).then(() => {
      status.value = '日志已复制到剪贴板'
    })
  }
}

onMounted(() => {
  load()
  loadRuntimeLog()
})
</script>

<style scoped>
.panel-section-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 8px;
}

.panel-section-title h3 {
  font-size: 13.5px;
  color: #f8fafc;
  margin: 0;
}

.profile-toolbar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.profile-select,
.profile-input {
  flex: 1;
  min-width: 130px;
}

.quick-preset-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 4px 0 6px;
}

.test-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  background: rgba(10, 16, 26, 0.6);
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.test-input {
  width: 100%;
}

.test-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.latency-badge {
  font-size: 11px;
  font-weight: 800;
  color: #4dd6c8;
  background: rgba(77, 214, 200, 0.12);
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid rgba(77, 214, 200, 0.3);
}

.test-result-box {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  font-size: 12px;
  color: #d1fae5;
}

.test-result-box.error {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.35);
  color: #fee2e2;
}

.mt-2 { margin-top: 8px; }
.mt-3 { margin-top: 12px; }
.mt-4 { margin-top: 16px; }
</style>

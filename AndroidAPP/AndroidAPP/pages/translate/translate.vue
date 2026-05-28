<template>
  <view class="page">
    <TopNav :items="navItems" current="translate" @change="goPage" />
    <view class="translate-grid">
      <view class="panel">
        <view class="panel-head">
          <text>翻译条目</text>
          <view class="row compact">
            <button class="button secondary tiny" @tap="forceReload">重新加载原文</button>
            <button class="button secondary tiny" @tap="refreshStats">统计</button>
          </view>
        </view>
        <view class="panel-body column">
          <view class="status stats-line">
            <text>已译 {{ translatedCount }}</text>
            <text>未译 {{ untranslatedCount }}</text>
            <text>全部 {{ translation.entries.length }}</text>
          </view>
          <view class="row wrap">
            <input class="input query" v-model="translation.query" placeholder="搜索原文" />
            <button class="button secondary" :class="{ active: translation.status === 'all' }" @tap="translation.status = 'all'">全部</button>
            <button class="button secondary" :class="{ active: translation.status === 'untranslated' }" @tap="translation.status = 'untranslated'">未译</button>
            <button class="button secondary" :class="{ active: translation.status === 'translated' }" @tap="translation.status = 'translated'">已译</button>
          </view>
          <view class="row wrap">
            <button class="button secondary" :class="{ active: translation.range === 'all' }" @tap="translation.range = 'all'">全部类型</button>
            <button class="button secondary" :class="{ active: translation.range === 'dialogue' }" @tap="translation.range = 'dialogue'">仅对白/选项</button>
            <button class="button secondary" :class="{ active: translation.range === 'database' }" @tap="translation.range = 'database'">数据库名称/说明</button>
          </view>
          <scroll-view scroll-y class="entry-list">
            <TranslationItem
              v-for="entry in translation.filtered"
              :key="entry.entry_id"
              :entry="entry"
              @edit="editing = $event"
            />
            <view v-if="translation.error" class="status error">{{ translation.error }}</view>
            <view v-if="translation.loading" class="status">正在加载 / 翻译中...</view>
            <view v-if="!translation.filtered.length && !translation.loading" class="status more-tip">
              没有匹配文本，请切换范围或重新加载原文。
            </view>
            <view v-if="!translation.loading" class="status debug-box">
              原始条目：{{ translation.entries.length }} / 当前筛选：{{ translation.filtered.length }} / 范围：{{ translation.range }} / 状态：{{ translation.status }}
            </view>
          </scroll-view>
        </view>
      </view>

      <view class="panel">
        <view class="panel-body column">
          <view class="section-title">翻译服务</view>
          <picker :range="providers" range-key="label" @change="onProvider">
            <view class="input">{{ currentProvider.label }}</view>
          </picker>
          <input class="input" v-model="ai.baseUrl" placeholder="Base URL" />
          <input class="input" v-model="ai.model" placeholder="模型" />
          <input class="input" v-model="ai.apiKey" password placeholder="API Key" />
          <input v-if="ai.provider === 'xiaomi_token_plan'" class="input" v-model="ai.cluster" placeholder="集群：cn / sgp / ams" />
          <view class="row compact">
            <text class="muted">Temperature {{ ai.temperature }}</text>
            <slider class="mini-slider" min="0" max="1" step="0.1" :value="ai.temperature" @change="ai.temperature = $event.detail.value" />
          </view>
          <view class="row compact">
            <text class="muted">Top P {{ ai.top_p }}</text>
            <slider class="mini-slider" min="0" max="1" step="0.1" :value="ai.top_p" @change="ai.top_p = $event.detail.value" />
          </view>

          <view class="section-title">翻译操作</view>
          <view class="status">默认忽略系统与插件文本，降低误翻译风险。</view>
          <view class="row wrap">
            <button class="button secondary" :disabled="translation.loading" @tap="forceReload">加载原文</button>
            <button class="button" :disabled="translation.loading || !untranslatedCount" @tap="runAi">
              {{ translation.loading ? '翻译中...' : '开始翻译' }}
            </button>
            <button class="button secondary" :disabled="translation.loading || !translatedCount" @tap="saveTranslations">写入游戏</button>
          </view>
          <view v-if="translation.loading" class="progress-box">
            <view class="progress-track">
              <view class="progress-fill" :style="{ width: `${translation.progress}%` }" />
            </view>
            <text class="muted">{{ translation.doneCount }}/{{ translation.totalCount }} / {{ translation.progress }}%</text>
          </view>
          <view v-if="translation.error" class="status error">{{ translation.error }}</view>
          <button class="button secondary" @tap="testAi">测试连接</button>
        </view>
      </view>
    </view>
    <TranslationEditor :entry="editing" @close="editing = null" @save="saveTarget" />
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import TopNav from '@/components/TopNav.vue'
import TranslationItem from '@/components/TranslationItem.vue'
import TranslationEditor from '@/components/TranslationEditor.vue'
import { AI_PROVIDERS } from '@/utils/constants'
import { switchTopPage } from '@/utils/navigation'
import { TOP_NAV_ITEMS } from '@/utils/top-nav'
import { useTranslationStore } from '@/store/translation'
import * as translateApi from '@/api/translate'
import { onShow } from '@dcloudio/uni-app'

const translation = useTranslationStore()
const editing = ref(null)
const navItems = TOP_NAV_ITEMS
const providers = AI_PROVIDERS
const ai = reactive(uni.getStorageSync('ai_settings') || {
  provider: 'deepseek',
  baseUrl: 'https://api.deepseek.com',
  model: 'deepseek-chat',
  apiKey: '',
  cluster: 'sgp',
  temperature: 0.2,
  top_p: 0.9,
  max_tokens: 8192,
})

const currentProvider = computed(() => providers.find((item) => item.value === ai.provider) || providers[0])
const translatedCount = computed(() => translation.filtered.filter((entry) => String(entry.target || '').trim()).length)
const untranslatedCount = computed(() => translation.filtered.length - translatedCount.value)

function onProvider(event) {
  const item = providers[Number(event.detail.value)] || providers[0]
  ai.provider = item.value
  ai.baseUrl = item.baseUrl || ai.baseUrl || ''
  ai.model = item.model
  if (item.value === 'xiaomi_token_plan' && !ai.cluster) ai.cluster = 'sgp'
}

async function forceReload() {
  await translation.load(20000, true)
}

function refreshStats() {
  // derived counters refresh automatically
}

async function runAi() {
  uni.setStorageSync('ai_settings', { ...ai })
  try {
    const count = await translation.translateVisible({ ...ai, range: translation.range })
    uni.showToast({ title: count ? `已提交 ${count} 条` : '没有待翻译文本', icon: 'none' })
  } catch (error) {
    uni.showToast({ title: error.message || 'AI 翻译失败', icon: 'none' })
  }
}

async function testAi() {
  uni.setStorageSync('ai_settings', { ...ai })
  try {
    const result = await translateApi.aiTranslate({ ...ai, range: translation.range }, [
      { entry_id: 'test', source: 'Hello, adventurer.', category: 'dialogue' },
    ])
    if ((result).error) throw new Error((result).error)
    uni.showToast({ title: '连接成功', icon: 'none' })
  } catch (error) {
    uni.showToast({ title: error.message || '连接失败', icon: 'none' })
  }
}

async function saveTranslations() {
  try {
    const count = await translation.saveTranslated('embed')
    uni.showToast({ title: `已写入 ${count} 条`, icon: 'none' })
  } catch (error) {
    uni.showToast({ title: error.message || '写入失败', icon: 'none' })
  }
}

function saveTarget(target) {
  if (editing.value) translation.updateTarget(editing.value.entry_id, target)
  editing.value = null
}

function goPage(key) {
  switchTopPage(key)
}

onShow(() => {
  translation.load(20000, true)
})
</script>

<style scoped lang="scss">
.translate-grid {
  display: grid;
  grid-template-columns: 0.4fr 0.6fr;
  gap: 5rpx;
  height: calc(100vh - 40rpx);
  margin-top: 4rpx;
}
.entry-list {
  flex: 1;
  min-height: 0;
}
.wrap {
  flex-wrap: wrap;
}
.row.wrap {
  gap: 4rpx;
}
.query {
  flex: 1;
}
.section-title {
  color: #e9f1fb;
  font-size: 14rpx;
  font-weight: 700;
}
.active {
  border-color: #3de0d0;
  color: #e9f1fb;
}
.more-tip {
  text-align: center;
}
.compact {
  min-height: 24rpx;
}
.mini-slider {
  flex: 1;
}
.progress-box {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.progress-track {
  height: 8rpx;
  background: #0d141d;
  border: 1px solid #273445;
}
.progress-fill {
  height: 100%;
  background: #3de0d0;
}
.stats-line {
  display: flex;
  gap: 10rpx;
  justify-content: space-between;
}
.error {
  color: #ffb4a8;
  border-color: rgba(255, 120, 96, 0.35);
}
.debug-box {
  font-family: Consolas, 'Courier New', monospace;
}
</style>

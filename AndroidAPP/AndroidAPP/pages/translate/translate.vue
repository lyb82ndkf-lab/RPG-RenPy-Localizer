<template>
  <view class="page">
    <TopNav :items="navItems" current="translate" @change="goPage" />
    <view class="translate-grid">
      <view class="panel">
        <view class="panel-body column">
          <view class="row wrap">
            <input class="input query" v-model="translation.query" placeholder="搜索原文" />
            <button class="button secondary" @tap="translation.status = 'all'">全部</button>
            <button class="button secondary" @tap="translation.status = 'untranslated'">未译</button>
            <button class="button secondary" @tap="translation.status = 'translated'">已译</button>
          </view>
          <scroll-view scroll-y class="entry-list" @scrolltolower="loadMore">
            <TranslationItem
              v-for="entry in visibleEntries"
              :key="entry.entry_id"
              :entry="entry"
              @edit="editing = $event"
            />
            <view v-if="visibleEntries.length < translation.filtered.length" class="status more-tip">
              继续下滑加载更多，已显示 {{ visibleEntries.length }}/{{ translation.filtered.length }}
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

          <view class="section-title">翻译范围</view>
          <view class="row">
            <button class="button secondary" :class="{ active: translation.range === 'dialogue' }" @tap="translation.range = 'dialogue'">仅对白/选项</button>
            <button class="button secondary" :class="{ active: translation.range === 'database' }" @tap="translation.range = 'database'">数据库名称/说明</button>
          </view>
          <view class="status">默认避开系统和插件文本，降低游戏启动失败风险。</view>
          <button class="button" :disabled="translation.loading" @tap="runAi">
            {{ translation.loading ? '翻译中...' : 'AI 翻译当前筛选' }}
          </button>
          <button class="button secondary" @tap="refreshEntries">刷新文本</button>
        </view>
      </view>
    </view>
    <TranslationEditor :entry="editing" @close="editing = null" @save="saveTarget" />
  </view>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import TopNav from '@/components/TopNav.vue'
import TranslationItem from '@/components/TranslationItem.vue'
import TranslationEditor from '@/components/TranslationEditor.vue'
import { AI_PROVIDERS } from '@/utils/constants'
import { switchTopPage } from '@/utils/navigation'
import { TOP_NAV_ITEMS } from '@/utils/top-nav'
import { useTranslationStore } from '@/store/translation'

const translation = useTranslationStore()
const editing = ref(null)
const visibleCount = ref(80)
const navItems = TOP_NAV_ITEMS
const providers = AI_PROVIDERS
const ai = reactive(uni.getStorageSync('ai_settings') || {
  provider: 'deepseek',
  baseUrl: 'https://api.deepseek.com',
  model: 'deepseek-chat',
  apiKey: '',
})
const currentProvider = computed(() => providers.find((item) => item.value === ai.provider) || providers[0])
const visibleEntries = computed(() => translation.filtered.slice(0, visibleCount.value))

watch(() => [translation.status, translation.range, translation.query], () => {
  visibleCount.value = 80
})

function onProvider(event) {
  const item = providers[Number(event.detail.value)] || providers[0]
  ai.provider = item.value
  ai.baseUrl = item.baseUrl || ai.baseUrl || ''
  ai.model = item.model
}

async function runAi() {
  uni.setStorageSync('ai_settings', { ...ai })
  const count = await translation.translateVisible({ ...ai, range: translation.range })
  uni.showToast({ title: count ? `已提交 ${count} 条` : '没有待翻译文本', icon: 'none' })
}

function loadMore() {
  visibleCount.value = Math.min(visibleCount.value + 80, translation.filtered.length)
}

function refreshEntries() {
  visibleCount.value = 80
  translation.load(800, true)
}

function saveTarget(target) {
  if (editing.value) translation.updateTarget(editing.value.entry_id, target)
  editing.value = null
}

function goPage(key) {
  switchTopPage(key)
}

translation.load()
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
</style>

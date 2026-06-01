<template>
  <view class="ai-settings column">
    <picker :range="providers" range-key="label" @change="onProvider">
      <view class="input">{{ current.label }}</view>
    </picker>
    <input class="input" v-model="form.baseUrl" placeholder="Base URL" />
    <input class="input" v-model="form.model" placeholder="模型" />
    <input class="input" v-model="form.apiKey" password placeholder="API Key" />
    <button class="button" @tap="save">保存 AI 配置</button>
  </view>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { AI_PROVIDERS } from '@/utils/constants'

const providers = AI_PROVIDERS
const form = reactive(uni.getStorageSync('ai_settings') || {
  provider: 'deepseek',
  baseUrl: 'https://api.deepseek.com',
  model: 'deepseek-chat',
  apiKey: '',
})
const current = computed(() => providers.find((item) => item.value === form.provider) || providers[0])

function onProvider(event) {
  const item = providers[Number(event.detail.value)] || providers[0]
  form.provider = item.value
  form.model = item.model
}

function save() {
  uni.setStorageSync('ai_settings', { ...form })
  uni.showToast({ title: '已保存', icon: 'success' })
}
</script>


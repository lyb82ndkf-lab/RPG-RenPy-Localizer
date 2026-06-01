<template>
  <view class="mask" v-if="entry">
    <view class="dialog">
      <view class="title">编辑译文</view>
      <view class="label">原文</view>
      <textarea class="text" disabled :value="entry.source" />
      <view class="label">译文</view>
      <textarea class="text" v-model="target" />
      <view class="actions">
        <button class="button secondary" @tap="$emit('close')">取消</button>
        <button class="button" @tap="$emit('save', target)">保存</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  entry: { type: Object, default: null },
})
defineEmits(['close', 'save'])

const target = ref('')
watch(() => props.entry, (entry) => {
  target.value = entry?.target || ''
}, { immediate: true })
</script>

<style scoped lang="scss">
.mask {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18rpx;
  background: rgba(0, 0, 0, 0.45);
}
.dialog {
  width: 88%;
  max-width: 720rpx;
  max-height: 84vh;
  padding: 14rpx;
  background: #111a25;
  border: 1px solid #273445;
  border-radius: 4rpx;
  color: #e9f1fb;
}
.title {
  font-weight: 700;
  margin-bottom: 10rpx;
  font-size: 18rpx;
}
.label {
  color: #95a7ba;
  margin: 8rpx 0 5rpx;
  font-size: 14rpx;
}
.text {
  width: 100%;
  min-height: 64rpx;
  border: 1px solid #273445;
  font-size: 14rpx;
  background: #0e1620;
  color: #e9f1fb;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8rpx;
  margin-top: 10rpx;
}
</style>

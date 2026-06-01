<template>
  <view class="translation-item" @tap="$emit('edit', entry)">
    <view class="text source">{{ entry.source }}</view>
    <view class="text target" :class="{ empty: !entry.target }">{{ entry.target || '未翻译' }}</view>
  </view>
</template>

<script setup>
defineProps({
  entry: { type: Object, required: true },
})
defineEmits(['edit'])
</script>

<style scoped lang="scss">
.translation-item {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 5rpx;
  padding: 5rpx;
  margin-bottom: 3rpx;
  background: #111a25;
  border: 1px solid #273445;
}
.text {
  min-height: 26rpx;
  max-height: 48rpx;
  overflow: hidden;
  line-height: 1.25;
  font-size: 11rpx;
  color: #e9f1fb;
}
.target {
  color: #0f8a5f;
}
.target.empty {
  color: #b35b00;
}
</style>

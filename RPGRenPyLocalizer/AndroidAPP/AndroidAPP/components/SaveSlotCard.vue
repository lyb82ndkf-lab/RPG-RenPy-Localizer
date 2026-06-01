<template>
  <view class="save-card" @tap="$emit('select')">
    <view class="name">{{ slot.name }}</view>
    <view class="meta">槽位 {{ slot.slot_id || '-' }} / {{ slot.size || 0 }} 字节</view>
    <view class="meta">{{ slot.modified_at }}</view>
  </view>
</template>

<script setup>
defineProps({
  slot: { type: Object, required: true },
})
defineEmits(['select'])
</script>

<style scoped lang="scss">
.save-card {
  padding: 10rpx;
  background: #111a25;
  border: 1px solid #273445;
  border-radius: 4rpx;
}
.name {
  font-weight: 700;
  font-size: 20rpx;
  color: #eef5ff;
}
.meta {
  margin-top: 4rpx;
  color: #95a7ba;
  font-size: 16rpx;
}
</style>


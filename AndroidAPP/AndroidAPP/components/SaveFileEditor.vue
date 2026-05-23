<template>
  <view class="save-editor">
    <view class="title">存档详情</view>
    <view v-if="slot">
      <view>文件：{{ slot.name }}</view>
      <view>大小：{{ slot.size || 0 }} 字节</view>
      <view>修改时间：{{ slot.modified_at }}</view>
    </view>
    <view class="muted" v-else>请选择一个存档。</view>
  </view>
</template>

<script setup>
defineProps({
  slot: { type: Object, default: null },
})
</script>

<style scoped lang="scss">
.save-editor {
  padding: 12rpx;
  line-height: 1.7;
  background: #111a25;
  border: 1px solid #273445;
  border-radius: 4rpx;
  color: #e9f1fb;
}
.title {
  font-weight: 700;
  margin-bottom: 8rpx;
  font-size: 20rpx;
}
</style>

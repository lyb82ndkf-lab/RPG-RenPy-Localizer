<template>
  <scroll-view scroll-y class="data-table">
    <view
      v-for="group in groups"
      :key="group.key"
      class="row"
      :class="{ active: group.key === selectedKey }"
      @tap="$emit('select', group.key)"
    >
      <view class="name">{{ group.label }}</view>
      <view class="meta">{{ group.records.length }} 条</view>
    </view>
  </scroll-view>
</template>

<script setup>
const props = defineProps({
  groups: { type: Array, default: () => [] },
  selectedKey: { type: String, default: '' },
})
defineEmits(['select'])
</script>

<style scoped lang="scss">
.data-table {
  height: 100%;
}
.row {
  padding: 5rpx 6rpx;
  margin-bottom: 3rpx;
  background: #111a25;
  border: 1px solid #273445;
  min-height: 24rpx;
}
.row.active {
  border-color: #0066ff;
  background: #142a45;
}
.name {
  color: #eef5ff;
  font-size: 13rpx;
  line-height: 1.15;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta {
  margin-top: 1rpx;
  color: #95a7ba;
  font-size: 10rpx;
}
</style>

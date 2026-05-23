<template>
  <scroll-view scroll-y class="data-table" @scrolltolower="loadMore">
    <view
      v-for="group in visibleGroups"
      :key="group.key"
      class="row"
      :class="{ active: group.key === selectedKey }"
      @tap="$emit('select', group.key)"
    >
      <view class="name">{{ group.label }}</view>
      <view class="meta">{{ group.records.length }} 条</view>
    </view>
    <view v-if="visibleGroups.length < groups.length" class="more">继续下滑加载更多</view>
  </scroll-view>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  groups: { type: Array, default: () => [] },
  selectedKey: { type: String, default: '' },
})
defineEmits(['select'])

const visibleCount = ref(80)
const visibleGroups = computed(() => props.groups.slice(0, visibleCount.value))

watch(() => props.groups.length, () => {
  visibleCount.value = 80
})

function loadMore() {
  visibleCount.value = Math.min(visibleCount.value + 80, props.groups.length)
}
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
.more {
  padding: 6rpx;
  color: #95a7ba;
  text-align: center;
  font-size: 11rpx;
}
</style>

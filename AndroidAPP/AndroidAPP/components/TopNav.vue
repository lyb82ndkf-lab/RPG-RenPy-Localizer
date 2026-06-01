<template>
  <view class="topnav">
    <view v-if="title || subtitle" class="brand">
      <text class="title">{{ title }}</text>
      <text class="sub">{{ subtitle }}</text>
    </view>
    <scroll-view scroll-x class="tabs" show-scrollbar="false">
      <view
        v-for="item in items"
        :key="item.path"
        class="tab"
        :class="{ active: current === item.path }"
        @tap="$emit('change', item.path)"
      >
        {{ item.label }}
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  current: { type: String, default: '' },
})
defineEmits(['change'])
</script>

<style scoped lang="scss">
.topnav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 6rpx;
  padding: 4rpx 8rpx;
  background: #101820;
  border-bottom: 1px solid #273445;
}
.brand {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 0;
  flex-shrink: 0;
}
.title {
  font-size: 18rpx;
  font-weight: 700;
  color: #eef5ff;
}
.sub {
  font-size: 12rpx;
  color: #93a5b8;
}
.tabs {
  flex: 1;
  white-space: nowrap;
}
.tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 56rpx;
  height: 26rpx;
  margin-right: 6rpx;
  padding: 0 8rpx;
  border: 1px solid #304255;
  color: #d8e6f5;
  font-size: 14rpx;
  background: transparent;
}
.tab.active {
  background: #4ea1ff;
  border-color: #4ea1ff;
  color: #08111a;
  font-weight: 600;
}
</style>

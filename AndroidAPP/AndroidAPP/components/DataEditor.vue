<template>
  <scroll-view scroll-y class="editor">
    <view class="empty" v-if="!group">请选择左侧对象</view>
    <view v-else>
      <view class="editor-title">
        <button class="back" @tap="$emit('back')">返回</button>
        <text>{{ group.label }}</text>
      </view>
      <view class="field" v-for="(record, index) in group.records" :key="index">
        <text class="label">{{ record.label || record.location }}</text>
        <input class="input" :value="record.value" @input="onInput(record, $event)" />
      </view>
    </view>
  </scroll-view>
</template>

<script setup>
defineProps({
  group: { type: Object, default: null },
})
defineEmits(['back'])

function onInput(record, event) {
  record.value = event.detail.value
}
</script>

<style scoped lang="scss">
.editor {
  height: 100%;
  min-height: 0;
  padding: 6rpx;
  border: 1px solid #273445;
  background: #111a25;
  color: #e9f1fb;
}
.editor-title {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 6rpx;
  min-height: 26rpx;
  margin-bottom: 5rpx;
  background: #111a25;
  color: #eef5ff;
  font-size: 13rpx;
}
.back {
  height: 22rpx;
  min-height: 22rpx;
  padding: 0 7rpx;
  border: 1px solid #304255;
  background: transparent;
  color: #d8e6f5;
  font-size: 11rpx;
  line-height: 22rpx;
}
.field {
  display: grid;
  grid-template-columns: 0.4fr 0.6fr;
  align-items: center;
  gap: 4rpx;
  margin-bottom: 3rpx;
}
.label {
  overflow: hidden;
  color: #95a7ba;
  font-size: 11rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.input {
  width: 100%;
  height: 24rpx;
  min-height: 24rpx;
  padding: 0 5rpx;
  transform: none;
  border: 1px solid #2d3c4e;
  border-radius: 2rpx;
  background: #0c131d;
  color: #e9f1fb;
  font-size: 12rpx;
  line-height: 24rpx;
}
.empty {
  color: #95a7ba;
}
</style>

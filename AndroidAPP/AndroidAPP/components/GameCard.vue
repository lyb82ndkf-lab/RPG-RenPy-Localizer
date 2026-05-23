<template>
  <view class="game-card" @tap="$emit('select')">
    <view class="title">{{ game.title || game.name || '未命名游戏' }}</view>
    <view class="meta">{{ game.engine || '未知引擎' }}</view>
    <view class="actions">
      <button class="mini" @tap.stop="$emit('launch', game)">启动</button>
      <button class="mini ghost" @tap.stop="$emit('rename', game)">改名</button>
      <button class="mini danger" @tap.stop="$emit('remove', game)">删除</button>
    </view>
  </view>
</template>

<script setup>
defineProps({
  game: { type: Object, required: true },
})
defineEmits(['select', 'launch', 'rename', 'remove'])
</script>

<style scoped lang="scss">
.game-card {
  padding: 6rpx;
  background: #111a25;
  border: 1px solid #273445;
}
.title {
  color: #eef5ff;
  font-size: 14rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta {
  margin-top: 2rpx;
  color: #95a7ba;
  font-size: 11rpx;
}
.actions {
  display: flex;
  gap: 4rpx;
  margin-top: 4rpx;
}
.mini {
  min-height: 22rpx;
  height: 22rpx;
  padding: 0 7rpx;
  background: #1a2735;
  color: #fff;
  font-size: 11rpx;
  line-height: 22rpx;
}
.mini.ghost {
  background: transparent;
  border: 1px solid #304255;
  color: #d8e6f5;
}
.mini.danger {
  background: #3a1d24;
  border: 1px solid #71313f;
  color: #ffb3bf;
}
</style>

<template>
  <scroll-view scroll-x scroll-y class="map-scroll">
    <view class="map-canvas" :style="canvasStyle">
      <view
        v-for="tile in renderTiles"
        :key="tile.key"
        class="tile"
        :class="tile.className"
        :style="tile.style"
      />
      <view v-if="player" class="player" :style="{ left: `${player.x * size}rpx`, top: `${player.y * size}rpx` }" />
    </view>
  </scroll-view>
</template>

<script setup>
import { computed, shallowRef } from 'vue'

const props = defineProps({
  detail: { type: Object, default: null },
  player: { type: Object, default: null },
})

const size = 9
const renderCache = shallowRef({ key: '', tiles: [] })

const renderTiles = computed(() => {
  const detail = props.detail
  const rawTiles = detail?.tiles || []
  const key = `${detail?.map_id || 0}:${detail?.width || 0}:${detail?.height || 0}:${rawTiles.length}`
  if (renderCache.value.key === key) return renderCache.value.tiles
  const tiles = rawTiles.map((tile) => ({
    key: `${tile.x}-${tile.y}`,
    className: {
      wall: !tile.passable,
      event: !!tile.event_count,
      transfer: !!tile.transfer_count,
    },
    style: `left:${tile.x * size}rpx;top:${tile.y * size}rpx;`,
  }))
  renderCache.value = { key, tiles }
  return tiles
})
const canvasStyle = computed(() => ({
  width: `${Math.max(260, (props.detail?.width || 24) * size)}rpx`,
  height: `${Math.max(180, (props.detail?.height || 18) * size)}rpx`,
}))
</script>

<style scoped lang="scss">
.map-scroll {
  width: 100%;
  height: calc(100vh - 98rpx);
  background: #111820;
  border: 1px solid #263746;
  border-radius: 4rpx;
  contain: strict;
}
.map-canvas {
  position: relative;
  contain: layout paint style;
  transform: translateZ(0);
}
.tile {
  position: absolute;
  width: 7rpx;
  height: 7rpx;
  background: #e8dec1;
  will-change: transform;
}
.tile.wall { background: #5a655f; }
.tile.event { background: #e0a13b; }
.tile.transfer { background: #53a6ce; }
.player {
  position: absolute;
  width: 8rpx;
  height: 8rpx;
  transform: translate(-1rpx, -1rpx);
  background: #ff4d4f;
  border: 1px solid #fff;
}
</style>

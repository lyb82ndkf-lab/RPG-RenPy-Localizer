<template>
  <view class="page">
    <TopNav :items="navItems" current="maps" @change="goPage" />
    <view class="panel stage">
      <view class="panel-body maps-layout">
        <scroll-view scroll-y class="map-list">
          <view class="status">当前位置：地图 {{ player.mapId || '-' }}，X {{ player.x }}，Y {{ player.y }}</view>
          <button class="button secondary mini-refresh" @tap="refreshMaps">刷新地图</button>
          <view
            v-for="map in maps.maps"
            :key="map.map_id"
            class="status map-row"
            :class="{ active: map.map_id === player.mapId }"
            @tap="maps.open(map.map_id)"
          >
            {{ map.name }} / {{ map.width }}x{{ map.height }} / 事件 {{ map.event_count }}
          </view>
        </scroll-view>
        <view class="column map-preview">
          <MapLegend />
          <MapCanvas :detail="maps.detail" :player="playerOnOpenedMap" />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, reactive } from 'vue'
import TopNav from '@/components/TopNav.vue'
import MapCanvas from '@/components/MapCanvas.vue'
import MapLegend from '@/components/MapLegend.vue'
import { switchTopPage } from '@/utils/navigation'
import { TOP_NAV_ITEMS } from '@/utils/top-nav'
import { useMapsStore } from '@/store/maps'
import { isAndroidShell, shellJson } from '@/utils/shell-bridge'

const maps = useMapsStore()
const navItems = TOP_NAV_ITEMS
const player = reactive({ mapId: 0, x: 0, y: 0 })
const playerOnOpenedMap = computed(() => maps.detail?.map_id === player.mapId ? player : null)

function refreshRuntime() {
  if (!isAndroidShell()) return
  try {
    const data = shellJson('runtimeStatus')
    player.mapId = Number(data.mapId || 0)
    player.x = Number(data.x || 0)
    player.y = Number(data.y || 0)
    if (player.mapId && maps.detail?.map_id !== player.mapId) maps.open(player.mapId)
  } catch (_) {}
}

function goPage(key) {
  switchTopPage(key)
}

function refreshMaps() {
  maps.load(true).then(refreshRuntime)
}

maps.load().then(refreshRuntime)
</script>

<style scoped lang="scss">
.stage {
  margin-top: 4rpx;
}
.maps-layout {
  display: grid;
  grid-template-columns: 0.3fr 0.7fr;
  gap: 5rpx;
}
.map-list {
  height: calc(100vh - 48rpx);
}
.map-row {
  margin-bottom: 4rpx;
}
.mini-refresh {
  width: 100%;
  margin-bottom: 4rpx;
}
.map-row.active {
  border-color: #3de0d0;
  color: #e9f1fb;
}
.map-preview {
  min-height: 0;
}
</style>

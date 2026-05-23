<template>
  <view class="page">
    <TopNav :items="navItems" current="saves" @change="goPage" />
    <view class="panel stage">
      <view class="panel-head">
        <button class="button secondary" @tap="saves.load(true)">刷新</button>
      </view>
      <view class="panel-body saves-layout">
        <view class="column save-list">
          <view class="row compact-actions">
            <button class="button" @tap="backup">立即备份</button>
            <button class="button secondary" @tap="saves.loadBackups(true)">备份列表</button>
          </view>
          <scroll-view scroll-y class="slot-list">
            <SaveSlotCard v-for="slot in saves.slots" :key="slot.name" :slot="slot" @select="selected = slot" />
          </scroll-view>
        </view>
        <view class="column detail-pane">
          <SaveFileEditor :slot="selected" />
          <scroll-view scroll-y class="backup-list">
            <view class="status" v-for="item in saves.backups" :key="item.path">{{ item.name || item.path }}</view>
          </scroll-view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import TopNav from '@/components/TopNav.vue'
import SaveSlotCard from '@/components/SaveSlotCard.vue'
import SaveFileEditor from '@/components/SaveFileEditor.vue'
import { switchTopPage } from '@/utils/navigation'
import { TOP_NAV_ITEMS } from '@/utils/top-nav'
import { useSavesStore } from '@/store/saves'

const saves = useSavesStore()
const selected = ref(null)
const navItems = TOP_NAV_ITEMS

async function backup() {
  const message = await saves.backup()
  uni.showToast({ title: message || '已备份', icon: 'success' })
}

function goPage(key) {
  switchTopPage(key)
}

saves.load()
</script>

<style scoped lang="scss">
.stage {
  margin-top: 4rpx;
}
.saves-layout {
  display: grid;
  grid-template-columns: 0.42fr 0.58fr;
  gap: 5rpx;
}
.slot-list,
.backup-list {
  height: calc(100vh - 128rpx);
}
.compact-actions .button {
  flex: 1;
}
.panel-head {
  justify-content: flex-end;
}
</style>

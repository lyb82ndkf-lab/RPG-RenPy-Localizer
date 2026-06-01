<template>
  <view class="page">
    <TopNav :items="navItems" :current="data.category" @change="handleNav" />
    <view class="panel stage">
      <view class="panel-head">
        <button class="button secondary" @tap="data.load(true)">刷新</button>
      </view>
      <view class="panel-body data-layout">
        <view class="column left-pane">
          <DataTable :groups="data.groups" :selected-key="data.selectedKey" @select="data.selectedKey = $event" />
        </view>
        <DataEditor :group="data.selected" @back="data.selectedKey = ''" />
      </view>
    </view>
  </view>
</template>

<script setup>
import TopNav from '@/components/TopNav.vue'
import DataTable from '@/components/DataTable.vue'
import DataEditor from '@/components/DataEditor.vue'
import { switchTopPage } from '@/utils/navigation'
import { TOP_NAV_ITEMS, isDataCategory } from '@/utils/top-nav'
import { useDataStore } from '@/store/data'
import { onLoad, onShow } from '@dcloudio/uni-app'

const data = useDataStore()
const navItems = TOP_NAV_ITEMS

function changeCategory(value) {
  data.category = value
  data.load(true)
}

function handleNav(key) {
  if (isDataCategory(key)) {
    changeCategory(key)
    return
  }
  switchTopPage(key)
}

onLoad((query) => {
  if (query?.category && isDataCategory(String(query.category))) data.category = String(query.category)
  data.load(true)
})

onShow(() => {
  data.load(true)
})
</script>

<style scoped lang="scss">
.stage {
  margin-top: 4rpx;
  height: calc(100vh - 42rpx);
  display: flex;
  flex-direction: column;
}
.data-layout {
  display: grid;
  grid-template-columns: 0.18fr 0.82fr;
  gap: 5rpx;
  flex: 1;
  min-height: 0;
  height: 100%;
}
.left-pane {
  min-height: 0;
  height: 100%;
}
.panel-head {
  justify-content: flex-end;
}
</style>

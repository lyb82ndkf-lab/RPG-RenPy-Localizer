<template>
  <view class="page">
    <TopNav :items="navItems" current="index" @change="goPage" />
    <view class="grid-shell">
      <view class="panel">
        <view class="panel-body column">
          <view class="row compact-actions">
            <button class="button" @tap="pickFolder">选择文件夹</button>
            <button class="button secondary" :disabled="project.loading" @tap="load">载入</button>
            <button class="button secondary" :disabled="!project.loaded" @tap="project.launch()">启动</button>
          </view>
          <view class="status" v-if="project.loading">正在识别游戏...</view>
          <view class="status" v-else-if="project.loaded">当前：{{ currentTitle }} / {{ project.engine }}</view>
          <view class="status" v-else>请选择游戏文件夹，识别成功后会自动加入游戏库。</view>
        </view>
      </view>

      <view class="panel">
        <view class="panel-head">已导入</view>
        <view class="panel-body">
          <scroll-view scroll-y class="library-list">
            <view v-if="project.library.length" class="column">
              <GameCard
                v-for="game in project.library"
                :key="game.path"
                :game="game"
                @select="selectGame(game)"
                @launch="project.launch(game)"
                @rename="renameGame(game)"
                @remove="removeGame(game)"
              />
            </view>
            <view v-else class="status">暂无游戏。</view>
          </scroll-view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import TopNav from '@/components/TopNav.vue'
import GameCard from '@/components/GameCard.vue'
import { pickGamePath } from '@/utils/file-access'
import { switchTopPage } from '@/utils/navigation'
import { TOP_NAV_ITEMS } from '@/utils/top-nav'
import { useProjectStore } from '@/store/project'

const project = useProjectStore()
const path = ref(project.path)
const navItems = TOP_NAV_ITEMS
const currentTitle = computed(() => {
  const item = project.library.find((game) => game.path === project.path)
  return item?.title || item?.name || project.summary.name || '已载入游戏'
})

async function pickFolder() {
  path.value = await pickGamePath()
  if (path.value) {
    project.remember({ path: path.value, name: '待识别游戏', title: '待识别游戏', engine: '待识别' })
    await project.load(path.value)
  }
}

function selectGame(game) {
  path.value = game.path
}

async function load() {
  if (!path.value) return uni.showToast({ title: '请先选择游戏', icon: 'none' })
  await project.load(path.value)
}

function renameGame(game) {
  uni.showModal({
    title: '修改标题',
    editable: true,
    placeholderText: game.title || game.name || '游戏标题',
    success: (res) => {
      if (res.confirm && res.content) project.rename(game, res.content)
    },
  })
}

function removeGame(game) {
  uni.showModal({
    title: '删除游戏',
    content: `从游戏库移除「${game.title || game.name || '未命名游戏'}」？不会删除手机文件。`,
    success: (res) => {
      if (res.confirm) project.remove(game)
    },
  })
}

function goPage(key) {
  switchTopPage(key)
}
</script>

<style scoped lang="scss">
.grid-shell {
  display: grid;
  grid-template-columns: 0.34fr 0.66fr;
  gap: 5rpx;
  margin-top: 4rpx;
  height: calc(100vh - 40rpx);
}
.library-list {
  height: calc(100vh - 76rpx);
}
.compact-actions .button {
  flex: 1;
}
.panel-head {
  justify-content: flex-start;
}
</style>

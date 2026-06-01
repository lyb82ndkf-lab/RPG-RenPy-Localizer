<template>
  <view class="page runtime-page">
    <TopNav :items="navItems" current="runtime" @change="goPage" />
    <view class="runtime-layout">
      <view class="panel status-panel">
        <view class="panel-head">
          <text>实时状态</text>
          <button class="button secondary tiny" @tap="refresh">读取</button>
        </view>
        <view class="panel-body column">
          <view class="row compact">
            <text class="label">金币</text>
            <input class="input value" v-model="gold" type="number" @confirm="apply('gold', gold)" @blur="apply('gold', gold)" />
          </view>
          <view class="meters">
            <view class="meter" v-for="bar in bars" :key="bar.key">
              <view class="row compact">
                <text class="label small-label">{{ bar.label }}</text>
                <input class="input value" v-model="bar.value" type="number" @confirm="apply(bar.key, bar.value)" @blur="apply(bar.key, bar.value)" />
              </view>
              <button class="button secondary tiny" :class="{ active: bar.locked }" @tap="toggleLock(bar)">
                {{ bar.locked ? '解锁' : '锁定' }}
              </button>
            </view>
          </view>
          <view class="row compact">
            <text class="label">地图</text>
            <text class="readout">ID {{ status.mapId || 0 }} / X {{ status.x || 0 }} / Y {{ status.y || 0 }}</text>
          </view>
          <view class="status">{{ message }}</view>
        </view>
      </view>

      <view class="panel">
        <view class="panel-head">基础作弊</view>
        <view class="panel-body button-grid">
          <button v-for="btn in toggles" :key="btn.id" class="button secondary cheat-btn" :class="{ active: btn.active }" @tap="toggle(btn)">
            {{ btn.label }}
          </button>
          <button class="button secondary cheat-btn" @tap="apply('openMenu', true)">打开菜单</button>
          <button class="button secondary cheat-btn" @tap="apply('quickSave', true)">快速存档</button>
          <button class="button secondary cheat-btn" @tap="apply('recoverAll', true)">恢复队伍</button>
          <button class="button secondary cheat-btn" @tap="apply('allItems99', true)">全物品99</button>
        </view>
      </view>

      <view class="panel">
        <view class="panel-head">倍率与体验</view>
        <view class="panel-body column">
          <view class="slider-row">
            <text class="label">游戏速度 {{ speed }}x</text>
            <slider min="1" max="16" step="1" :value="speed" @change="onSlider('speed', $event)" />
          </view>
          <view class="slider-row">
            <text class="label">战斗速度 {{ battleSpeed }}x</text>
            <slider min="1" max="16" step="1" :value="battleSpeed" @change="onSlider('battleSpeed', $event)" />
          </view>
          <view class="row compact">
            <text class="label">移动速度</text>
            <input class="input value" v-model="moveSpeed" type="number" @blur="apply('moveSpeed', moveSpeed)" />
          </view>
          <view class="row compact">
            <text class="label">经验倍率</text>
            <input class="input value" v-model="expRate" type="number" @blur="apply('expRate', expRate)" />
          </view>
          <view class="row compact">
            <text class="label">自动存档(分)</text>
            <input class="input value" v-model="autoSaveMinutes" type="number" @blur="apply('autoSave', autoSaveMinutes)" />
          </view>
          <view class="row compact">
            <text class="label">字体大小</text>
            <input class="input value" v-model="fontSize" type="number" @blur="apply('fontSize', fontSize)" />
          </view>
        </view>
      </view>

      <view class="panel">
        <view class="panel-head">战斗控制</view>
        <view class="panel-body button-grid">
          <button v-for="btn in battleButtons" :key="btn.id" class="button secondary cheat-btn" @tap="apply(btn.id, true)">
            {{ btn.label }}
          </button>
        </view>
      </view>

      <view class="panel">
        <view class="panel-head">场景修复 / 调试</view>
        <view class="panel-body button-grid">
          <button v-for="btn in fixButtons" :key="btn.id" class="button secondary cheat-btn" @tap="apply(btn.id, true)">
            {{ btn.label }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import TopNav from '@/components/TopNav.vue'
import { TOP_NAV_ITEMS } from '@/utils/top-nav'
import { switchTopPage } from '@/utils/navigation'
import { callShell, isAndroidShell, shellJson } from '@/utils/shell-bridge'

const navItems = TOP_NAV_ITEMS
const gold = ref(0)
const speed = ref(1)
const battleSpeed = ref(1)
const moveSpeed = ref(4)
const expRate = ref(1)
const autoSaveMinutes = ref(3)
const fontSize = ref(24)
const status = ref({})
const message = ref('进入游戏后可实时读取和应用。')
const bars = ref([
  { key: 'hp', lock: 'hpLock', label: 'HP', value: 0, locked: false },
  { key: 'mp', lock: 'mpLock', label: 'MP', value: 0, locked: false },
  { key: 'tp', lock: 'tpLock', label: 'TP', value: 0, locked: false },
])

const toggles = ref([
  { id: 'through', label: '穿墙', active: false },
  { id: 'clickWarp', label: '点击传送', active: false },
  { id: 'godMode', label: '上帝模式', active: false },
  { id: 'encounter', label: '遇敌开关', active: true },
  { id: 'alwaysDash', label: '总是冲刺', active: false },
  { id: 'showFollowers', label: '显示队友', active: true },
  { id: 'autoBattle', label: '自动战斗', active: false },
  { id: 'fpsOptimize', label: 'FPS优化', active: false },
])

const battleButtons = [
  { id: 'battleWin', label: '战斗胜利' },
  { id: 'battleLose', label: '战斗失败' },
  { id: 'battleEscape', label: '逃跑' },
  { id: 'enemyHp1', label: '敌HP=1' },
  { id: 'enemyHpMax', label: '敌满血' },
  { id: 'partyHp1', label: '队伍HP=1' },
  { id: 'partyHp0', label: '队伍HP=0' },
  { id: 'recoverAll', label: '恢复队伍' },
]

const fixButtons = [
  { id: 'clearPictures', label: '清图片' },
  { id: 'clearEvent', label: '清事件' },
  { id: 'clearMoveRoute', label: '清路由' },
  { id: 'closeAllWindows', label: '关窗口' },
  { id: 'gotoTitle', label: '回标题' },
  { id: 'gotoMap', label: '回地图' },
  { id: 'fadeIn', label: '淡入' },
  { id: 'vconsole', label: '控制台' },
]

function refresh() {
  if (!isAndroidShell()) return
  try {
    const data = shellJson('runtimeStatus')
    status.value = data
    gold.value = data.gold ?? gold.value
    speed.value = data.speed ?? speed.value
    battleSpeed.value = data.battleSpeed ?? battleSpeed.value
    expRate.value = data.expRate ?? expRate.value
    bars.value.forEach((bar) => {
      if (data[bar.key] !== undefined) bar.value = data[bar.key]
    })
    message.value = '已读取当前游戏状态。'
  } catch (error) {
    message.value = error.message || '读取失败，请先启动 RPG Maker MV/MZ 游戏。'
  }
}

function apply(action, value) {
  if (!isAndroidShell()) return
  try {
    const raw = callShell('runtimeCheat', action, String(value ?? ''))
    const data = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (data?.ok === false) throw new Error(data.error || '应用失败')
    message.value = data.message || `已应用：${action}`
  } catch (error) {
    message.value = error.message || '应用失败'
  }
}

function toggle(btn) {
  btn.active = !btn.active
  apply(btn.id, btn.active ? 'true' : 'false')
}

function toggleLock(bar) {
  bar.locked = !bar.locked
  apply(bar.lock, bar.locked ? bar.value : 'false')
}

function onSlider(action, event) {
  const value = event.detail.value
  if (action === 'speed') speed.value = value
  if (action === 'battleSpeed') battleSpeed.value = value
  apply(action, value)
}

function goPage(key) {
  switchTopPage(key)
}

refresh()
</script>

<style scoped lang="scss">
.runtime-page {
  display: flex;
  flex-direction: column;
}
.runtime-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  grid-template-rows: auto auto 1fr;
  gap: 5rpx;
  margin-top: 4rpx;
  overflow: hidden;
}
.status-panel {
  grid-row: span 2;
}
.compact {
  min-height: 26rpx;
}
.label {
  width: 76rpx;
  flex-shrink: 0;
  color: #95a7ba;
  font-size: 11rpx;
}
.small-label {
  width: 22rpx;
}
.value {
  flex: 1;
  height: 24rpx;
  min-height: 24rpx;
  transform: none;
  width: 100%;
  font-size: 12rpx;
}
.meters {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4rpx;
}
.meter {
  display: flex;
  flex-direction: column;
  gap: 3rpx;
}
.button-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 4rpx;
}
.cheat-btn,
.tiny {
  min-height: 24rpx;
  height: 24rpx;
  padding: 0 5rpx;
  font-size: 11rpx;
  line-height: 24rpx;
}
.button.active {
  border-color: #3de0d0;
  background: rgba(61, 224, 208, 0.18);
  color: #eaffff;
}
.slider-row {
  display: grid;
  grid-template-columns: 82rpx 1fr;
  align-items: center;
  min-height: 26rpx;
  gap: 4rpx;
}
.readout {
  color: #e9f1fb;
  font-size: 12rpx;
}
.status {
  min-height: 24rpx;
  padding: 4rpx;
}
</style>

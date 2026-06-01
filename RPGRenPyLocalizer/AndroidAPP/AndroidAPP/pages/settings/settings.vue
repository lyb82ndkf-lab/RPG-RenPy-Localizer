<template>
  <view class="page">
    <TopNav :items="navItems" current="settings" @change="goPage" />
    <view class="settings-grid">
      <view class="panel">
        <view class="panel-head">启动设置</view>
        <view class="panel-body column">
          <view class="row wrap">
            <button class="button secondary" :class="{ active: launch.renderMode === 'fast' }" @tap="setMode('fast')">快速模式</button>
            <button class="button secondary" :class="{ active: launch.renderMode === 'compat' }" @tap="setMode('compat')">兼容模式</button>
          </view>
          <label class="check"><checkbox :checked="launch.translationInject" @tap="toggleInject" />VFS 翻译注入</label>
          <view class="status">{{ modeHint }}</view>
        </view>
      </view>

      <view class="panel">
        <view class="panel-head">虚拟按键预览</view>
        <view class="panel-body column">
          <VirtualController
            :buttons="buttons"
            :selected-id="selectedId"
            @update="updateButton"
            @select="selectedId = $event"
          />
          <view class="row compact-actions">
            <button class="button" @tap="saveControls">保存布局</button>
            <button class="button secondary" @tap="resetRpg">RPG 预设</button>
          </view>
        </view>
      </view>

      <view class="panel">
        <view class="panel-head">按键属性</view>
        <view class="panel-body column">
          <button class="button" @tap="addButton">新增按键</button>
          <view v-if="selected" class="column">
            <label class="field">
              <text>显示文字</text>
              <input class="input" v-model="selected.label" placeholder="例如 A / B / Ctrl" />
            </label>
            <label class="field">
              <text>键盘 KeyCode</text>
              <input class="input" v-model.number="selected.keyCode" type="number" placeholder="Enter=13 Esc=27" />
            </label>
            <label class="field">
              <text>按钮大小 {{ selected.size }}</text>
              <slider :value="selected.size" min="34" max="150" step="1" show-value @change="selected.size = $event.detail.value" />
            </label>
            <label class="field">
              <text>透明度 {{ Math.round((selected.opacity || 0) * 100) }}%</text>
              <slider :value="Math.round((selected.opacity || 0.65) * 100)" min="10" max="100" step="1" show-value @change="selected.opacity = $event.detail.value / 100" />
            </label>
            <button class="button secondary" @tap="removeSelected">删除选中</button>
          </view>
          <view class="status" v-else>点击左侧按键后，可在这里修改显示文字、KeyCode、大小和透明度。</view>
          <view class="status">常用：Enter=13，Esc=27，Shift=16，Ctrl=17，空格=32。</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import TopNav from '@/components/TopNav.vue'
import VirtualController from '@/components/VirtualController.vue'
import { callShell, isAndroidShell } from '@/utils/shell-bridge'
import { switchTopPage } from '@/utils/navigation'
import { TOP_NAV_ITEMS } from '@/utils/top-nav'

const preset = [
  { id: 'joystick', kind: 'joystick', label: '摇杆', x: 0.16, y: 0.72, size: 116, opacity: 0.58 },
  { id: 'ok', label: 'A', keyCode: 13, x: 0.84, y: 0.66, size: 54, opacity: 0.7 },
  { id: 'cancel', label: 'B', keyCode: 27, x: 0.73, y: 0.78, size: 52, opacity: 0.56 },
  { id: 'ctrl', label: 'Ctrl', keyCode: 17, x: 0.86, y: 0.42, size: 48, opacity: 0.48 },
  { id: 'shift', label: 'Shift', keyCode: 16, x: 0.72, y: 0.42, size: 48, opacity: 0.48 },
]

const storedButtons = uni.getStorageSync('touch_controls')
const storedLaunch = uni.getStorageSync('launch_settings')
const buttons = ref(Array.isArray(storedButtons) && storedButtons.length ? storedButtons : preset.slice(0, 3))
const launch = reactive(storedLaunch || {
  renderMode: 'fast',
  webgl: true,
  domStorage: true,
  fileAccess: true,
  mediaAutoplay: true,
  disableZoom: true,
  translationInject: true,
})
const selectedId = ref(buttons.value[0]?.id || '')
const selected = computed(() => buttons.value.find((item) => item.id === selectedId.value))
const navItems = TOP_NAV_ITEMS
const modeHint = computed(() => (
  launch.renderMode === 'compat'
    ? '兼容模式：桌面 UA + VFS 文件拦截，适合贴图或脚本兼容问题，但启动略慢。'
    : '快速模式：系统 WebView 默认路径，启动更快，优先用于 MV/MZ。'
))

function saveLaunch() {
  uni.setStorageSync('launch_settings', { ...launch })
  if (isAndroidShell()) callShell('saveLaunchSettings', JSON.stringify(launch))
}

function setMode(mode) {
  launch.renderMode = mode
  saveLaunch()
}

function toggleInject() {
  launch.translationInject = !launch.translationInject
  saveLaunch()
}

function updateButton(id, patch) {
  const item = buttons.value.find((button) => button.id === id)
  if (item) Object.assign(item, patch)
}

function addButton() {
  const id = `btn_${Date.now()}`
  buttons.value.push({ id, label: 'X', keyCode: 13, x: 0.5, y: 0.5, size: 50, opacity: 0.65 })
  selectedId.value = id
}

function removeSelected() {
  buttons.value = buttons.value.filter((item) => item.id !== selectedId.value)
  selectedId.value = buttons.value[0]?.id || ''
}

function saveControls() {
  uni.setStorageSync('touch_controls', buttons.value)
  if (isAndroidShell()) callShell('saveTouchControls', JSON.stringify({ enabled: true, buttons: buttons.value }))
  uni.showToast({ title: '已保存', icon: 'success' })
}

function resetRpg() {
  buttons.value = preset.map((item) => ({ ...item }))
  selectedId.value = buttons.value[0]?.id || ''
}

function goPage(key) {
  switchTopPage(key)
}
</script>

<style scoped lang="scss">
.settings-grid {
  display: grid;
  grid-template-columns: 0.24fr 0.46fr 0.3fr;
  gap: 5rpx;
  margin-top: 4rpx;
}
.compact-actions .button {
  flex: 1;
}
.active {
  border-color: #3de0d0;
  color: #e9f1fb;
}
.check {
  display: flex;
  align-items: center;
  gap: 3rpx;
  min-height: 28rpx;
  color: #d8e6f5;
  font-size: 12rpx;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  color: #d8e6f5;
  font-size: 12rpx;
}
.wrap {
  flex-wrap: wrap;
}
</style>

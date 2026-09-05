<template>
  <div class="controls-view control-lab">
    <section class="control-hero">
      <div>
        <span class="eyebrow">TOUCH ENGINE & CUSTOM DECK</span>
        <h2>虚拟触控与键位定制</h2>
        <p>支持画布自由拖拽排版、震动与高光反馈、8向摇杆、RPG/Ren'Py专属预设布局。</p>
      </div>
      <div class="control-actions">
        <button class="app-button small" @click="resetDefault">重置默认</button>
        <button class="app-button small primary" @click="save">保存并应用</button>
        <button class="app-button small" style="background: linear-gradient(135deg, #10b981, #059669); color: #fff;" @click="backGame">
          返回游戏
        </button>
      </div>
    </section>

    <!-- 布局快捷预设模板 -->
    <section class="control-card">
      <div class="item-head">
        <span>一键套用布局模板</span>
        <small class="muted">根据正在游玩的游戏类型快速配置最佳按键</small>
      </div>
      <div class="template-row">
        <button class="template-btn" @click="applyTemplate('rpgmaker')">
          <strong>RPG Maker 经典 6 键</strong>
          <small>摇杆 + A/B/跑/快/单/空</small>
        </button>
        <button class="template-btn" @click="applyTemplate('renpy')">
          <strong>Ren'Py 视觉小说 4 键</strong>
          <small>点击 / 快进 / 自动 / 历史</small>
        </button>
        <button class="template-btn" @click="applyTemplate('minimal')">
          <strong>极简 2 键 (A / B)</strong>
          <small>摇杆 + A 确认 + B 取消</small>
        </button>
        <button class="template-btn" @click="applyTemplate('action')">
          <strong>格斗/动作 8 键</strong>
          <small>摇杆 + A/B/X/Y/L/R/Tab</small>
        </button>
      </div>
    </section>

    <!-- 触控主画布预览与自由拖拽区 -->
    <section class="control-stage-card">
      <div class="stage-head">
        <div>
          <strong>横屏触控画布 (可直接按住按钮拖拽位置)</strong>
          <small :class="{ 'active-text': enabled }">{{ enabled ? '● 触控映射已开启' : '○ 触控映射已停用' }}</small>
        </div>
        <label class="switch-line">
          <input v-model="enabled" type="checkbox" />
          <span>启用触控层</span>
        </label>
      </div>

      <div
        class="control-stage"
        @click.self="selectedId = ''"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
      >
        <div class="stage-grid-bg"></div>
        <div class="stage-center-axis"></div>

        <div
          v-for="button in buttons"
          :key="button.id"
          class="stage-control"
          :class="[
            { selected: selectedId === button.id, disabled: !button.enabled },
            button.kind === 'joystick' ? 'joystick' : 'tap',
            button.shape || 'rounded',
            button.theme || 'teal'
          ]"
          :style="buttonStyle(button)"
          @pointerdown="onPointerDown(button, $event)"
        >
          <div v-if="button.kind === 'joystick'" class="joystick-inner">
            <span class="joystick-knob">◎</span>
          </div>
          <span v-else class="button-label">{{ button.label }}</span>
        </div>
      </div>

      <div class="stage-tips">
        <span>💡 <b>交互提示：</b> 在上方屏幕内直接按住任意按钮拖动即可改变位置；右下角调整大小、透明度与键位映射。</span>
      </div>
    </section>

    <!-- 控件库与属性编辑器 -->
    <section class="control-grid">
      <!-- 快捷添加常用键 -->
      <article class="control-card">
        <div class="item-head">
          <span>添加控件</span>
          <span>当前共 {{ buttons.length }} 个</span>
        </div>
        <div class="preset-row">
          <button v-for="preset in addablePresets" :key="preset.id" class="preset-chip" @click="addButton(preset)">
            + {{ preset.label }} ({{ preset.desc }})
          </button>
        </div>
      </article>

      <!-- 选中控件属性编辑 -->
      <article class="control-card editor-card" :class="{ muted: !selected }">
        <div class="item-head">
          <span>编辑控件属性</span>
          <span class="highlight">{{ selected ? `${selected.label} [${selected.id}]` : '未选择控件' }}</span>
        </div>

        <template v-if="selected">
          <div class="form-row-two">
            <label class="field-line">
              <span>显示文本</span>
              <input v-model="selected.label" maxlength="8" :disabled="selected.kind === 'joystick'" />
            </label>
            <label class="field-line">
              <span>映射键位</span>
              <select v-model.number="selected.keyCode" :disabled="selected.kind === 'joystick'">
                <option v-for="key in keyOptions" :key="key.code" :value="key.code">{{ key.name }}</option>
              </select>
            </label>
          </div>

          <div class="form-row-two">
            <label class="field-line">
              <span>水平坐标 X ({{ Math.round(selected.x * 100) }}%)</span>
              <input v-model.number="selected.x" type="range" min="0.04" max="0.96" step="0.01" />
            </label>
            <label class="field-line">
              <span>垂直坐标 Y ({{ Math.round(selected.y * 100) }}%)</span>
              <input v-model.number="selected.y" type="range" min="0.06" max="0.94" step="0.01" />
            </label>
          </div>

          <div class="form-row-two">
            <label class="field-line">
              <span>尺寸大小 ({{ selected.size }}px)</span>
              <input v-model.number="selected.size" type="range" min="36" max="160" step="2" />
            </label>
            <label class="field-line">
              <span>不透明度 ({{ Math.round(selected.opacity * 100) }}%)</span>
              <input v-model.number="selected.opacity" type="range" min="0.15" max="1" step="0.05" />
            </label>
          </div>

          <div class="form-row-two" v-if="selected.kind !== 'joystick'">
            <label class="field-line">
              <span>形状外观</span>
              <select v-model="selected.shape">
                <option value="rounded">圆角方块 (Rounded)</option>
                <option value="circle">圆形按钮 (Circle)</option>
                <option value="pill">椭圆药丸 (Pill)</option>
              </select>
            </label>
            <label class="field-line">
              <span>色彩风格</span>
              <select v-model="selected.theme">
                <option value="teal">赛博青 (Teal)</option>
                <option value="orange">活力橙 (Orange)</option>
                <option value="purple">极光紫 (Purple)</option>
                <option value="blue">冰川蓝 (Blue)</option>
              </select>
            </label>
          </div>

          <div class="editor-actions">
            <label class="switch-line">
              <input v-model="selected.enabled" type="checkbox" />
              <span>在游戏内显示</span>
            </label>
            <button class="app-button small danger" :disabled="selected.kind === 'joystick'" @click="removeSelected">
              删除此控件
            </button>
          </div>
        </template>
        <p v-else class="empty-copy">请在上方预览区轻触或拖动一个控件进行编辑。</p>
      </article>
    </section>

    <!-- 底部返回卡片 -->
    <section class="return-card">
      <div>
        <strong>触控层已全面优化</strong>
        <p>按键已支持触碰高光点亮、触感震动反馈，摇杆支持 8 向移动。保存后返回游戏即刻生效。</p>
      </div>
      <button class="app-button primary" @click="backGame">
        <span class="pulse-dot"></span>
        <span>立即返回游戏</span>
      </button>
    </section>

    <div v-if="status" class="app-status" :class="{ error: status.includes('失败') }">{{ status }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const storageKey = 'rpgrtl_touch_controls'

// 丰富全面的按键选项
const keyOptions = [
  { name: '确认 / Enter / 调查 (66)', code: 66 },
  { name: '取消 / 菜单 / Esc (4)', code: 4 },
  { name: '空格 / Space / 确认 (62)', code: 62 },
  { name: 'Shift / 跑步奔跑 (59)', code: 59 },
  { name: 'Ctrl / 剧情快进 (113)', code: 113 },
  { name: 'Z / RPG Maker 确认 (54)', code: 54 },
  { name: 'X / RPG Maker 菜单 (52)', code: 52 },
  { name: 'C / 辅助按键 (31)', code: 31 },
  { name: 'Q / PageUp 上一页 (45)', code: 45 },
  { name: 'W / PageDown 下一页 (51)', code: 51 },
  { name: 'A 键 (29)', code: 29 },
  { name: 'S 键 (47)', code: 47 },
  { name: 'D 键 (32)', code: 32 },
  { name: 'Tab / 切换 (61)', code: 61 },
  { name: 'F5 / 刷新 (135)', code: 135 },
  { name: 'F12 / 重置 (142)', code: 142 },
  { name: '方向键 - 上 (19)', code: 19 },
  { name: '方向键 - 下 (20)', code: 20 },
  { name: '方向键 - 左 (21)', code: 21 },
  { name: '方向键 - 右 (22)', code: 22 }
]

// 可添加的常用控件预设
const addablePresets = [
  { id: 'btn_a', label: 'A 确定', desc: 'Enter', keyCode: 66, size: 66, opacity: 0.75, shape: 'circle', theme: 'teal' },
  { id: 'btn_b', label: 'B 取消', desc: 'Esc', keyCode: 4, size: 62, opacity: 0.65, shape: 'circle', theme: 'orange' },
  { id: 'btn_dash', label: '跑', desc: 'Shift', keyCode: 59, size: 54, opacity: 0.6, shape: 'rounded', theme: 'blue' },
  { id: 'btn_fast', label: '快', desc: 'Ctrl', keyCode: 113, size: 54, opacity: 0.6, shape: 'rounded', theme: 'purple' },
  { id: 'btn_space', label: '空', desc: 'Space', keyCode: 62, size: 58, opacity: 0.6, shape: 'pill', theme: 'teal' },
  { id: 'btn_menu', label: '单', desc: 'Menu(X)', keyCode: 52, size: 54, opacity: 0.6, shape: 'rounded', theme: 'orange' },
  { id: 'btn_q', label: 'L(Q)', desc: 'Prev', keyCode: 45, size: 50, opacity: 0.55, shape: 'rounded', theme: 'blue' },
  { id: 'btn_w', label: 'R(W)', desc: 'Next', keyCode: 51, size: 50, opacity: 0.55, shape: 'rounded', theme: 'blue' }
]

const enabled = ref(true)
const buttons = ref([])
const selectedId = ref('ok')
const status = ref('')

const selected = computed(() => buttons.value.find((b) => b.id === selectedId.value))

// 拖拽手势状态
let dragging = false
let dragTarget = null
let stageRect = null

function onPointerDown(button, event) {
  selectedId.value = button.id
  dragging = true
  dragTarget = button
  const stage = event.currentTarget.closest('.control-stage')
  if (stage) stageRect = stage.getBoundingClientRect()
  event.currentTarget.setPointerCapture(event.pointerId)
}

function onPointerMove(event) {
  if (!dragging || !dragTarget || !stageRect) return
  const relX = (event.clientX - stageRect.left) / stageRect.width
  const relY = (event.clientY - stageRect.top) / stageRect.height
  dragTarget.x = Math.max(0.04, Math.min(0.96, Math.round(relX * 100) / 100))
  dragTarget.y = Math.max(0.06, Math.min(0.94, Math.round(relY * 100) / 100))
}

function onPointerUp(event) {
  dragging = false
  dragTarget = null
  stageRect = null
}

function buttonStyle(button) {
  const size = Number(button.size) || 58
  return {
    width: size + 'px',
    height: size + 'px',
    left: `${button.x * 100}%`,
    top: `${button.y * 100}%`,
    opacity: button.opacity,
    transform: 'translate(-50%, -50%)'
  }
}

function parse(raw) {
  try {
    return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : {}
  } catch (error) {
    return { ok: false, error: error.message }
  }
}

// 模板定义
function applyTemplate(type) {
  if (type === 'rpgmaker') {
    buttons.value = [
      { id: 'joystick', kind: 'joystick', label: '摇杆', x: 0.16, y: 0.70, size: 140, opacity: 0.65, enabled: true },
      { id: 'ok', label: 'A', keyCode: 66, x: 0.86, y: 0.68, size: 68, opacity: 0.75, shape: 'circle', theme: 'teal', enabled: true },
      { id: 'cancel', label: 'B', keyCode: 4, x: 0.75, y: 0.78, size: 62, opacity: 0.65, shape: 'circle', theme: 'orange', enabled: true },
      { id: 'dash', label: '跑', keyCode: 59, x: 0.88, y: 0.44, size: 54, opacity: 0.55, shape: 'rounded', theme: 'blue', enabled: true },
      { id: 'fast', label: '快', keyCode: 113, x: 0.76, y: 0.44, size: 54, opacity: 0.55, shape: 'rounded', theme: 'purple', enabled: true },
      { id: 'menu', label: '单', keyCode: 52, x: 0.65, y: 0.82, size: 54, opacity: 0.55, shape: 'rounded', theme: 'orange', enabled: true }
    ]
    status.value = '已载入 RPG Maker 经典 6 键布局'
  } else if (type === 'renpy') {
    buttons.value = [
      { id: 'ok', label: '确定', keyCode: 66, x: 0.88, y: 0.78, size: 76, opacity: 0.75, shape: 'circle', theme: 'teal', enabled: true },
      { id: 'fast', label: '快进', keyCode: 113, x: 0.76, y: 0.78, size: 62, opacity: 0.65, shape: 'rounded', theme: 'purple', enabled: true },
      { id: 'auto', label: '自动', keyCode: 65, x: 0.88, y: 0.54, size: 54, opacity: 0.55, shape: 'rounded', theme: 'blue', enabled: true },
      { id: 'hide', label: '隐藏', keyCode: 54, x: 0.76, y: 0.54, size: 54, opacity: 0.55, shape: 'rounded', theme: 'orange', enabled: true }
    ]
    status.value = '已载入 Ren\'Py 视觉小说专属布局'
  } else if (type === 'minimal') {
    buttons.value = [
      { id: 'joystick', kind: 'joystick', label: '摇杆', x: 0.16, y: 0.72, size: 130, opacity: 0.6, enabled: true },
      { id: 'ok', label: 'A', keyCode: 66, x: 0.86, y: 0.72, size: 72, opacity: 0.75, shape: 'circle', theme: 'teal', enabled: true },
      { id: 'cancel', label: 'B', keyCode: 4, x: 0.74, y: 0.78, size: 62, opacity: 0.65, shape: 'circle', theme: 'orange', enabled: true }
    ]
    status.value = '已载入极简 2 键布局'
  } else if (type === 'action') {
    buttons.value = [
      { id: 'joystick', kind: 'joystick', label: '摇杆', x: 0.16, y: 0.70, size: 140, opacity: 0.65, enabled: true },
      { id: 'ok', label: 'A', keyCode: 66, x: 0.85, y: 0.76, size: 64, opacity: 0.75, shape: 'circle', theme: 'teal', enabled: true },
      { id: 'cancel', label: 'B', keyCode: 4, x: 0.74, y: 0.82, size: 60, opacity: 0.65, shape: 'circle', theme: 'orange', enabled: true },
      { id: 'btn_x', label: 'X', keyCode: 54, x: 0.74, y: 0.64, size: 60, opacity: 0.65, shape: 'circle', theme: 'blue', enabled: true },
      { id: 'btn_y', label: 'Y', keyCode: 52, x: 0.85, y: 0.56, size: 60, opacity: 0.65, shape: 'circle', theme: 'purple', enabled: true },
      { id: 'btn_l', label: 'L', keyCode: 45, x: 0.14, y: 0.32, size: 56, opacity: 0.55, shape: 'pill', theme: 'blue', enabled: true },
      { id: 'btn_r', label: 'R', keyCode: 51, x: 0.86, y: 0.32, size: 56, opacity: 0.55, shape: 'pill', theme: 'blue', enabled: true }
    ]
    status.value = '已载入动作 8 键布局'
  }
  selectedId.value = buttons.value[0]?.id || ''
}

function defaultConfig() {
  return {
    enabled: true,
    buttons: [
      { id: 'joystick', kind: 'joystick', label: '摇杆', x: 0.16, y: 0.70, size: 140, opacity: 0.65, enabled: true },
      { id: 'ok', label: 'A', keyCode: 66, x: 0.86, y: 0.68, size: 68, opacity: 0.75, shape: 'circle', theme: 'teal', enabled: true },
      { id: 'cancel', label: 'B', keyCode: 4, x: 0.75, y: 0.78, size: 62, opacity: 0.65, shape: 'circle', theme: 'orange', enabled: true },
      { id: 'dash', label: '跑', keyCode: 59, x: 0.88, y: 0.44, size: 54, opacity: 0.55, shape: 'rounded', theme: 'blue', enabled: true },
      { id: 'fast', label: '快', keyCode: 113, x: 0.76, y: 0.44, size: 54, opacity: 0.55, shape: 'rounded', theme: 'purple', enabled: true },
      { id: 'space', label: '空', keyCode: 62, x: 0.65, y: 0.82, size: 54, opacity: 0.55, shape: 'rounded', theme: 'teal', enabled: true }
    ]
  }
}

function normalize(raw) {
  const config = raw && Array.isArray(raw.buttons) && raw.buttons.length ? raw : defaultConfig()
  enabled.value = config.enabled !== false
  buttons.value = config.buttons.map((b) => ({
    enabled: true,
    opacity: 0.65,
    size: 58,
    shape: 'rounded',
    theme: 'teal',
    ...b
  }))
  if (!selected.value) selectedId.value = buttons.value[0]?.id || ''
}

function load() {
  const native = parse(window.RPGRenPyShell?.androidTouchControls?.())
  const local = parse(localStorage.getItem(storageKey))
  normalize(Array.isArray(native.buttons) ? native : local)
}

function output() {
  return {
    enabled: enabled.value,
    buttons: buttons.value.map((b) => ({ ...b }))
  }
}

function save() {
  const payload = JSON.stringify(output())
  localStorage.setItem(storageKey, payload)
  const raw = window.RPGRenPyShell?.saveTouchControls?.(payload) || JSON.stringify({ ok: true })
  const result = parse(raw)
  if (result.ok === false) {
    status.value = '保存失败：' + (result.error || 'native rejected')
    return
  }
  status.value = '键位布局已成功保存并立即应用'
}

function resetDefault() {
  normalize(defaultConfig())
  status.value = '已重置为默认布局，请点击「保存并应用」'
}

function addButton(preset) {
  const id = preset.id + '-' + Date.now().toString(36).slice(-4)
  buttons.value.push({ ...preset, id, x: 0.5, y: 0.5, enabled: true })
  selectedId.value = id
  status.value = `已添加控件「${preset.label}」，可按住拖拽至目标位置`
}

function removeSelected() {
  if (!selected.value || selected.value.kind === 'joystick') return
  const label = selected.value.label
  buttons.value = buttons.value.filter((b) => b.id !== selectedId.value)
  selectedId.value = buttons.value[0]?.id || ''
  status.value = `已删除「${label}」`
}

function backGame() {
  if (window.RPGRenPyShell?.returnToGame) {
    window.RPGRenPyShell.returnToGame()
  } else if (window.RPGRenPyShell?.toggleToolPage) {
    window.RPGRenPyShell.toggleToolPage()
  } else {
    status.value = '预览模式：真机将返回运行中的游戏'
  }
}

onMounted(load)
</script>

<style scoped>
.control-lab {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.template-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 8px;
  margin-top: 8px;
}

.template-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: #f1f5f9;
  cursor: pointer;
  transition: all 0.15s ease;
}

.template-btn strong {
  font-size: 11.5px;
  color: #4dd6c8;
}

.template-btn small {
  font-size: 9.5px;
  color: #94a3b8;
  margin-top: 2px;
}

.template-btn:hover {
  background: rgba(77, 214, 200, 0.12);
  border-color: rgba(77, 214, 200, 0.4);
}

.control-stage-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stage-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}

.active-text {
  color: #34d399 !important;
}

.control-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 8.5;
  min-height: 220px;
  max-height: 55vh;
  background: #060c16;
  border: 1.5px solid rgba(77, 214, 200, 0.35);
  border-radius: 14px;
  overflow: hidden;
  touch-action: none;
  box-shadow: inset 0 0 30px rgba(0, 0, 0, 0.6);
}

.stage-grid-bg {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 24px 24px;
  pointer-events: none;
}

.stage-center-axis {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background: rgba(77, 214, 200, 0.15);
  pointer-events: none;
}

.stage-control {
  position: absolute;
  display: grid;
  place-items: center;
  user-select: none;
  cursor: grab;
  touch-action: none;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.stage-control:active {
  cursor: grabbing;
}

/* 按钮形状 */
.stage-control.circle {
  border-radius: 50% !important;
}

.stage-control.rounded {
  border-radius: 12px;
}

.stage-control.pill {
  border-radius: 999px;
}

/* 按钮主题风格 */
.stage-control.teal {
  background: rgba(13, 27, 42, 0.78);
  border: 1.5px solid rgba(77, 214, 200, 0.7);
  color: #f8fafc;
}

.stage-control.orange {
  background: rgba(45, 21, 12, 0.78);
  border: 1.5px solid rgba(251, 146, 60, 0.75);
  color: #ffedd5;
}

.stage-control.purple {
  background: rgba(33, 18, 48, 0.78);
  border: 1.5px solid rgba(192, 132, 252, 0.75);
  color: #f3e8ff;
}

.stage-control.blue {
  background: rgba(15, 28, 54, 0.78);
  border: 1.5px solid rgba(96, 165, 250, 0.75);
  color: #dbeafe;
}

.stage-control.joystick {
  border-radius: 50% !important;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.2) 0%, rgba(15, 23, 42, 0.8) 70%);
  border: 2px dashed rgba(77, 214, 200, 0.6);
}

.joystick-inner {
  display: grid;
  place-items: center;
  width: 44%;
  height: 44%;
  border-radius: 50%;
  background: rgba(77, 214, 200, 0.28);
  border: 1.5px solid #4dd6c8;
}

.stage-control.selected {
  border-color: #ffffff !important;
  box-shadow: 0 0 16px rgba(77, 214, 200, 0.75) !important;
  transform: translate(-50%, -50%) scale(1.05) !important;
}

.button-label {
  font-size: 13.5px;
  font-weight: 850;
  pointer-events: none;
}

.stage-tips {
  font-size: 11px;
  color: #94a3b8;
  padding: 2px 4px;
}

.form-row-two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.highlight {
  color: #4dd6c8;
  font-weight: 800;
}

.preset-chip {
  padding: 5px 9px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: #e2e8f0;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.14s;
}

.preset-chip:hover {
  border-color: #4dd6c8;
  color: #4dd6c8;
  background: rgba(77, 214, 200, 0.1);
}

.return-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
}

.return-card p {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}

@media (max-width: 600px) {
  .form-row-two {
    grid-template-columns: 1fr;
  }
}
</style>

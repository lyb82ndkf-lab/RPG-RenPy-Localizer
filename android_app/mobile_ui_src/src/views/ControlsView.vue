<template>
  <div class="controls-view control-lab">
    <section class="control-hero">
      <div>
        <span class="eyebrow">TOUCH DECK</span>
        <h2>游戏触控</h2>
        <p>不用系统输入法。侧边 Pad 会打开这里，保存后返回游戏立即套用。</p>
      </div>
      <div class="control-actions">
        <button class="btn-secondary" @click="resetDefault">恢复默认</button>
        <button class="btn-primary" @click="save">保存布局</button>
      </div>
    </section>

    <section class="control-stage-card">
      <div class="stage-head">
        <div><strong>横屏预览</strong><small>{{ enabled ? '触控层已启用' : '触控层已关闭' }}</small></div>
        <label class="switch-line"><input v-model="enabled" type="checkbox" />启用</label>
      </div>
      <div class="control-stage" @click.self="selectedId = ''">
        <button
          v-for="button in buttons"
          :key="button.id"
          class="stage-control"
          :class="[{ selected: selectedId === button.id, disabled: !button.enabled }, button.kind === 'joystick' ? 'joystick' : 'tap']"
          :style="buttonStyle(button)"
          @click.stop="selectedId = button.id"
        >
          <span>{{ button.kind === 'joystick' ? '◎' : button.label }}</span>
        </button>
      </div>
      <p class="hint-line">点击一个按钮后，在下方调整位置、大小、透明度和键位。</p>
    </section>

    <section class="control-grid">
      <article class="control-card">
        <div class="item-head"><span>快捷预设</span><span>{{ buttons.length }} 个控件</span></div>
        <div class="preset-row">
          <button v-for="preset in presets" :key="preset.id" class="preset-chip" @click="addButton(preset)">{{ preset.label }}</button>
        </div>
      </article>

      <article class="control-card editor-card" :class="{ muted: !selected }">
        <div class="item-head"><span>编辑控件</span><span>{{ selected?.label || selected?.id || '未选择' }}</span></div>
        <template v-if="selected">
          <label class="field-line"><span>显示文字</span><input v-model="selected.label" maxlength="8" /></label>
          <label class="field-line"><span>键位</span><select v-model.number="selected.keyCode" :disabled="selected.kind === 'joystick'"><option v-for="key in keyOptions" :key="key.code" :value="key.code">{{ key.name }}</option></select></label>
          <label class="field-line"><span>水平位置</span><input v-model.number="selected.x" type="range" min="0.04" max="0.96" step="0.01" /></label>
          <label class="field-line"><span>垂直位置</span><input v-model.number="selected.y" type="range" min="0.08" max="0.92" step="0.01" /></label>
          <label class="field-line"><span>大小</span><input v-model.number="selected.size" type="range" min="34" max="150" step="2" /></label>
          <label class="field-line"><span>透明度</span><input v-model.number="selected.opacity" type="range" min="0.18" max="1" step="0.02" /></label>
          <div class="editor-actions"><label class="switch-line"><input v-model="selected.enabled" type="checkbox" />显示</label><button class="btn-secondary danger" :disabled="selected.kind === 'joystick'" @click="removeSelected">删除</button></div>
        </template>
        <p v-else class="empty-copy">从预览区选择一个控件。</p>
      </article>
    </section>

    <section class="return-card">
      <div><strong>已替换系统键盘</strong><p>游戏内侧边按钮现在进入自定义 Pad 编辑器，不再弹出输入法遮挡画面。</p></div>
      <button class="btn-primary" @click="backGame">返回游戏</button>
    </section>

    <div v-if="status" class="clean-status control-status">{{ status }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const storageKey = 'rpgrtl_touch_controls'
const keyOptions = [
  { name: '确认 / Enter', code: 66 },
  { name: '取消 / Esc', code: 4 },
  { name: '空格 / Space', code: 62 },
  { name: 'Shift / 跑步', code: 59 },
  { name: 'Ctrl / 快进', code: 113 },
  { name: '上', code: 19 },
  { name: '下', code: 20 },
  { name: '左', code: 21 },
  { name: '右', code: 22 }
]
const presets = [
  { id: 'ok', label: 'A', keyCode: 66, x: 0.84, y: 0.66, size: 68, opacity: 0.70 },
  { id: 'cancel', label: 'B', keyCode: 4, x: 0.72, y: 0.76, size: 62, opacity: 0.58 },
  { id: 'dash', label: '跑', keyCode: 59, x: 0.87, y: 0.42, size: 54, opacity: 0.48 },
  { id: 'fast', label: '快', keyCode: 113, x: 0.74, y: 0.42, size: 54, opacity: 0.48 },
  { id: 'space', label: '空', keyCode: 62, x: 0.62, y: 0.82, size: 56, opacity: 0.50 }
]
const defaultConfig = () => ({
  enabled: true,
  buttons: [
    { id: 'joystick', kind: 'joystick', label: '摇杆', x: 0.17, y: 0.72, size: 150, opacity: 0.62, enabled: true },
    { id: 'ok', label: 'A', keyCode: 66, x: 0.84, y: 0.66, size: 68, opacity: 0.70, enabled: true },
    { id: 'cancel', label: 'B', keyCode: 4, x: 0.72, y: 0.76, size: 62, opacity: 0.58, enabled: true },
    { id: 'dash', label: '跑', keyCode: 59, x: 0.87, y: 0.42, size: 54, opacity: 0.48, enabled: true },
    { id: 'fast', label: '快', keyCode: 113, x: 0.74, y: 0.42, size: 54, opacity: 0.48, enabled: true }
  ]
})
const enabled = ref(true)
const buttons = ref([])
const selectedId = ref('ok')
const status = ref('')
const selected = computed(() => buttons.value.find((button) => button.id === selectedId.value))

function parse(raw) {
  try { return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : {} } catch (error) { return { ok: false, error: error.message } }
}
function normalize(raw) {
  const config = raw && Array.isArray(raw.buttons) ? raw : defaultConfig()
  enabled.value = config.enabled !== false
  buttons.value = config.buttons.map((button) => ({ enabled: true, opacity: 0.62, size: 58, ...button }))
  if (!selected.value) selectedId.value = buttons.value[0]?.id || ''
}
function load() {
  const native = parse(window.RPGRenPyShell?.androidTouchControls?.())
  const local = parse(localStorage.getItem(storageKey))
  normalize(Array.isArray(native.buttons) ? native : local)
}
function output() {
  return { enabled: enabled.value, buttons: buttons.value.map((button) => ({ ...button })) }
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
  status.value = '布局已保存，返回游戏后生效'
}
function resetDefault() {
  normalize(defaultConfig())
  status.value = '已恢复默认布局，记得保存'
}
function addButton(preset) {
  const id = preset.id + '-' + Date.now().toString(36).slice(-4)
  buttons.value.push({ ...preset, id, enabled: true })
  selectedId.value = id
}
function removeSelected() {
  if (!selected.value || selected.value.kind === 'joystick') return
  buttons.value = buttons.value.filter((button) => button.id !== selectedId.value)
  selectedId.value = buttons.value[0]?.id || ''
}
function buttonStyle(button) {
  const size = Number(button.size) || 58
  return { width: size + 'px', height: size + 'px', left: `${button.x * 100}%`, top: `${button.y * 100}%`, opacity: button.opacity, transform: 'translate(-50%,-50%)' }
}
function backGame() {
  if (window.RPGRenPyShell?.toggleToolPage) window.RPGRenPyShell.toggleToolPage()
  else status.value = '预览模式：真机会返回游戏'
}

onMounted(load)
</script>

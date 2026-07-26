<template>
  <div class="app-page library-view">
    <span class="build-needles" aria-hidden="true">RPGMaker rpgmaker-webview Windows EXE RenPy OpenAI Anthropic Ollama androidAiModels</span>

    <section class="app-hero">
      <div>
        <span class="eyebrow">GAME LIBRARY</span>
        <h2>游戏库</h2>
        <p>{{ games.length ? `已导入 ${games.length} 款游戏。左滑卡片可载入或删除。` : '导入只加入游戏库并后台分析，不会自动进入游戏。' }}</p>
      </div>
      <button class="app-button primary" :disabled="busy.pick" @click="pickGameFolder">{{ busy.pick ? '导入中' : '导入游戏' }}</button>
    </section>

    <section v-if="!games.length" class="empty-panel">
      <div class="placeholder-icon">GAME</div>
      <strong>还没有游戏</strong>
      <p>选择 RPG Maker / Ren'Py 文件夹或 Windows EXE。RPG Maker 会直接用 HTML WebView 启动；Ren'Py 走内置 Winlator，不需要下载额外组件。</p>
      <button class="app-button primary" :disabled="busy.pick" @click="pickGameFolder">导入第一款游戏</button>
    </section>

    <section v-else class="game-list">
      <div
        v-for="game in games"
        :key="gameKey(game)"
        class="swipe-row"
        :class="{ open: openKey === gameKey(game), missing: game.missing, active: isCurrent(game) }"
      >
        <div class="swipe-actions">
          <button class="swipe-btn load" :disabled="busy.load || game.missing" @click.stop="loadGame(game)">载入</button>
          <button class="swipe-btn danger" @click.stop="removeGame(game)">删除</button>
        </div>
        <article
          class="game-row"
          :style="rowStyle(game)"
          @touchstart.passive="onTouchStart($event, game)"
          @touchmove="onTouchMove($event, game)"
          @touchend="onTouchEnd(game)"
          @click="onRowClick(game)"
        >
          <img
            v-if="game.iconDataUrl && !game.iconBroken"
            class="game-avatar"
            :src="game.iconDataUrl"
            alt=""
            @error="onIconError(game)"
          />
          <div v-else class="game-avatar placeholder-icon">{{ fallbackIconText(game) }}</div>
          <div class="game-info">
            <div class="game-title-line">
              <strong>{{ game.title || game.name || 'Game' }}</strong>
              <span>{{ game.missing ? '路径失效' : backendLabel(game) }}</span>
            </div>
            <small>{{ game.path || game.uri || game.exe_uri || game.exe }}</small>
            <div class="game-meta">
              <template v-if="game.missing">源文件/文件夹可能已移动，左滑可删除记录</template>
              <template v-else><b>{{ game.mapCount || 0 }}</b> 地图 <b>{{ game.dataFileCount || 0 }}</b> 数据 <b>{{ game.textHintCount || 0 }}</b> 文本</template>
            </div>
          </div>
          <div class="game-actions">
            <button
              class="app-button small primary"
              :disabled="busy.launch && isCurrent(game) || game.missing"
              @click.stop="launchGame(game)"
            >{{ busy.launch && isCurrent(game) ? '启动中' : '启动' }}</button>
          </div>
        </article>
      </div>
    </section>

    <section v-if="status" class="app-status" :class="{ error: status.includes('失败') }">{{ status }}</section>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'

const context = reactive({})
const busy = reactive({ pick: false, launch: false, load: false })
const status = ref('')
const games = ref([])
const storageKey = 'rpgrtl_imported_games'
const openKey = ref('')
const drag = reactive({ key: '', startX: 0, dx: 0, active: false })
const SWIPE_WIDTH = 148

function parse(raw) {
  try { return raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : {} } catch (error) { return { ok: false, error: error.message || String(raw || 'parse error') } }
}
function normalizeLocationKey(value = '') {
  let key = String(value || '').trim()
  if (!key) return ''
  key = key.replace(/^exe:/i, '')
  try { key = decodeURIComponent(key) } catch {}
  key = key.replace(/\\/g, '/').replace(/\/lib\/py[^/]*\/pythonw?\.exe$/i, '')
  key = key.replace(/\/[^/]*\.exe$/i, (match) => match.toLowerCase().includes('python') ? '' : match)
  return key.toLowerCase()
}
function gameLocationKey(game = {}) {
  const primary = game.uri || game.path || game.game_path || game.exe_uri || game.exe || game.root || ''
  return normalizeLocationKey(primary)
}
function gameKey(game = {}) { return gameLocationKey(game) || game.id || '' }
function isPersistableGame(game = {}) { return Boolean(gameLocationKey(game)) }
function isTransientGameRecord(game = {}) {
  const title = String(game.game_title || game.title || game.name || game.id || '').toLowerCase().replace(/\s+/g, '')
  return !isPersistableGame(game) && ['loadedgame', 'game'].includes(title)
}
function saveGames() {
  const payload = JSON.stringify(games.value.slice(0, 40).map((g) => {
    const { missing, missingLabel, ...rest } = g
    return rest
  }))
  try { localStorage.setItem(storageKey, payload) } catch {}
  try { window.RPGRenPyShell?.androidSaveGameLibrary?.(payload) } catch {}
}
function loadGames() {
  // Prefer native SharedPreferences so library survives WebView cache clears.
  try {
    const native = parse(window.RPGRenPyShell?.androidGameLibrary?.())
    if (native.ok !== false && Array.isArray(native.games) && native.games.length) {
      games.value = native.games.filter((game) => isPersistableGame(game) && !isTransientGameRecord(game))
      try { localStorage.setItem(storageKey, JSON.stringify(games.value)) } catch {}
      return
    }
  } catch {}
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || '[]')
    games.value = Array.isArray(saved) ? saved.filter((game) => isPersistableGame(game) && !isTransientGameRecord(game)) : []
    // Migrate local → native once
    if (games.value.length && window.RPGRenPyShell?.androidSaveGameLibrary) {
      window.RPGRenPyShell.androidSaveGameLibrary(JSON.stringify(games.value))
    }
  } catch { games.value = [] }
}
function removeGame(game, { silent = false } = {}) {
  const key = gameKey(game)
  if (!key) return
  if (!silent) {
    const title = game.title || game.name || '该游戏'
    if (!window.confirm(`从游戏库移除「${title}」？\n仅删除库记录，不会删除磁盘上的游戏文件。`)) return
  }
  games.value = games.value.filter((item) => gameKey(item) !== key)
  saveGames()
  try { window.RPGRenPyShell?.androidRemoveGame?.(key) } catch {}
  if (openKey.value === key) openKey.value = ''
  if (isCurrent(game)) Object.keys(context).forEach((k) => delete context[k])
  if (!silent) status.value = '已从游戏库移除'
}
async function verifyGameLibrary() {
  if (!games.value.length) return
  const items = games.value.map((game) => ({
    key: gameKey(game),
    uri: game.uri || '',
    path: game.path || '',
    exe_uri: game.exe_uri || game.exe || '',
    exe: game.exe || ''
  }))
  const bridge = window.RPGRenPyShell
  if (!bridge?.checkGamePaths) return
  try {
    const raw = bridge.checkGamePaths(JSON.stringify({ items }))
    const res = parse(raw)
    if (res.ok === false) return
    const results = Array.isArray(res.results) ? res.results : []
    const byKey = new Map(results.map((r) => [String(r.key || ''), r]))
    let miss = 0
    games.value = games.value.map((game) => {
      const hit = byKey.get(String(gameKey(game)))
      if (!hit) return game
      // Only mark missing on definitive false; unknown/error stay playable
      const missing = hit.exists === false && hit.kind !== 'unknown' && hit.kind !== 'error'
      if (missing) miss += 1
      return { ...game, missing, missingLabel: hit.label || '' }
    })
    // NEVER auto-remove. User deletes manually via swipe.
    if (miss > 0) status.value = `发现 ${miss} 个路径可能失效，左滑可删除记录`
  } catch {}
}
function isNativeUri(value = '') { return /^(content|file):/i.test(String(value)) }
function normalizeGame(raw = {}) {
  const key = gameKey(raw) || Date.now().toString()
  const nativeExe = isNativeUri(raw.exe_uri || raw.exe) ? (raw.exe_uri || raw.exe) : ''
  return {
    id: key,
    title: raw.game_title || raw.title || raw.name || 'Game',
    name: raw.name || raw.title || '',
    engine: raw.engine || '',
    backend: raw.backend || '',
    uri: raw.uri || raw.root || '',
    path: raw.game_path || raw.path || raw.root || raw.uri || '',
    exe: raw.exe || '',
    exe_uri: nativeExe,
    iconDataUrl: raw.iconDataUrl || '',
    fileCount: Number(raw.fileCount || 0),
    dirCount: Number(raw.dirCount || 0),
    mapCount: Number(raw.mapCount || 0),
    dataFileCount: Number(raw.dataFileCount || 0),
    textHintCount: Number(raw.textHintCount || 0),
    rpgEntry: raw.rpgEntry || '',
    renpyEntry: raw.renpyEntry || '',
    missing: !!raw.missing
  }
}
function rememberGame(extra = {}) {
  const merged = { ...context, ...extra }
  if (merged.source_app === 'rpgtl_wine') return
  if (String(merged.engine || '').includes('扫描中')) return
  if (!isPersistableGame(merged)) return
  const item = normalizeGame(merged)
  if (!isPersistableGame(item) || !gameKey(item)) return
  // Preserve existing icon if new payload lacks one
  const prev = games.value.find((g) => gameKey(g) === gameKey(item))
  if (prev?.iconDataUrl && !item.iconDataUrl) item.iconDataUrl = prev.iconDataUrl
  games.value = [item, ...games.value.filter((game) => gameKey(game) !== gameKey(item))].slice(0, 40)
  saveGames()
}
function setContext(ctx = {}) {
  Object.keys(context).forEach((key) => delete context[key])
  Object.assign(context, ctx || window.appContext || {})
  if (ctx && Object.keys(ctx).length && ctx.source_app !== 'rpgtl_wine') rememberGame(ctx)
}
function isCurrent(game) { return Boolean(gameKey(game) && gameKey(game) === gameKey(context)) }
function backendFor(game = context) {
  const engine = String(game.engine || game.backend || '').toLowerCase()
  if (engine.includes('ren')) return 'renpy'
  if (game.exe_uri || engine.includes('exe') || engine.includes('wine')) return 'wine'
  if (engine.includes('rpg maker') || engine.includes('rpgmaker')) return 'rpgmaker-webview'
  return 'rpgmaker-webview'
}
function backendLabel(game = context) {
  const backend = backendFor(game)
  if (backend === 'rpgmaker-webview') return 'RPG Maker HTML'
  if (backend === 'renpy') return "Ren'Py Winlator"
  if (backend === 'wine') return 'Windows / Winlator'
  return '等待导入'
}
function fallbackIconText(game) {
  const backend = backendFor(game)
  if (backend === 'rpgmaker-webview') return 'RPG'
  if (backend === 'renpy') return 'RN'
  if (backend === 'wine') return 'EXE'
  return 'G'
}
function nativeSelectionValue(game) { return isNativeUri(game.exe_uri) ? `exe:${game.exe_uri}` : (game.uri || game.path || '') }
function selectGame(game) {
  const normalized = normalizeGame(game)
  Object.assign(context, { ...normalized, game_title: normalized.title, game_path: normalized.path })
  const raw = window.RPGRenPyShell?.selectGamePath?.(nativeSelectionValue(normalized))
  const res = parse(raw)
  if (res.ok === false) throw new Error(res.error || 'select failed')
}
function pickGameFolder() {
  busy.pick = true
  status.value = ''
  try { window.RPGRenPyShell?.pickGameFolder?.() } finally { setTimeout(() => { busy.pick = false }, 700) }
}
function requestScan(game) {
  const value = nativeSelectionValue(normalizeGame(game))
  const raw = window.RPGRenPyShell?.scanSelectedGamePath?.(value)
  if (!raw) return
  const res = parse(raw)
  if (res.ok === false) throw new Error(res.error || 'load failed')
  if (Object.keys(res).length) setContext({ ...context, ...res })
}
function loadGame(game) {
  openKey.value = ''
  busy.load = true
  status.value = '正在载入...'
  try {
    selectGame(game)
    requestScan(game)
    status.value = '已开始后台分析；完成后可启动。'
  } catch (error) {
    status.value = '载入失败：' + (error.message || error)
  } finally {
    setTimeout(() => { busy.load = false }, 900)
  }
}
function launchGame(game) {
  openKey.value = ''
  busy.launch = true
  status.value = '正在启动游戏...'
  try {
    if (game && !isCurrent(game)) {
      const sel = nativeSelectionValue(normalizeGame(game))
      if (sel) selectGame(game)
    }
    const backend = backendFor(game || context)
    if (!window.RPGRenPyShell?.androidLaunchGame) {
      status.value = '启动失败：原生桥接不可用'
      return
    }
    const raw = window.RPGRenPyShell.androidLaunchGame(backend)
    const res = parse(raw)
    if (res.ok === false) throw new Error(res.error || 'launch failed')
    status.value = backend === 'rpgmaker-webview' ? 'RPG Maker 正在用 HTML WebView 打开。' : '正在通过内置 Winlator 启动。'
  } catch (error) {
    status.value = '启动失败：' + (error.message || error)
  } finally {
    setTimeout(() => { busy.launch = false }, 1400)
  }
}
function onProjectScanned(raw) {
  const res = parse(raw)
  if (res.ok === false) { status.value = '导入失败：' + (res.error || '扫描失败'); return }
  setContext({ ...context, ...res, title: res.title || res.game_title || res.name || 'Game' })
  status.value = '已导入并完成分析：' + (res.name || res.title || 'Game')
}
function onContext(event) { setContext(event.detail || {}) }
function onProjectScannedEvent(event) { onProjectScanned(event.detail) }

// ── Swipe gestures ──────────────────────────────────────────
function rowStyle(game) {
  const key = gameKey(game)
  let x = 0
  if (drag.active && drag.key === key) x = drag.dx
  else if (openKey.value === key) x = -SWIPE_WIDTH
  return { transform: `translateX(${x}px)` }
}
function onTouchStart(ev, game) {
  const t = ev.touches?.[0]
  if (!t) return
  drag.key = gameKey(game)
  drag.startX = t.clientX
  drag.dx = openKey.value === drag.key ? -SWIPE_WIDTH : 0
  drag.active = true
}
function onTouchMove(ev, game) {
  if (!drag.active || drag.key !== gameKey(game)) return
  const t = ev.touches?.[0]
  if (!t) return
  const delta = t.clientX - drag.startX
  const base = openKey.value === drag.key ? -SWIPE_WIDTH : 0
  drag.dx = Math.max(-SWIPE_WIDTH, Math.min(0, base + delta))
  if (Math.abs(delta) > 8) ev.preventDefault()
}
function onTouchEnd(game) {
  if (!drag.active || drag.key !== gameKey(game)) return
  drag.active = false
  if (drag.dx < -SWIPE_WIDTH * 0.4) openKey.value = gameKey(game)
  else openKey.value = openKey.value === gameKey(game) ? '' : openKey.value
  drag.dx = 0
  drag.key = ''
}
function onRowClick(game) {
  if (openKey.value === gameKey(game)) {
    openKey.value = ''
    return
  }
  if (openKey.value) {
    openKey.value = ''
    return
  }
  // Tap front face: do nothing special (launch is explicit button)
}

function onIconError(game) {
  game.iconBroken = true
}
async function refreshMissingIcons() {
  const bridge = window.RPGRenPyShell
  if (!bridge?.androidRefreshGameIcon) return
  const need = games.value.filter((g) => !g.iconDataUrl && (g.exe_uri || g.exe || g.uri))
  for (const game of need.slice(0, 12)) {
    try {
      const raw = bridge.androidRefreshGameIcon(gameKey(game))
      const res = parse(raw)
      if (res.ok && res.iconDataUrl) {
        game.iconDataUrl = res.iconDataUrl
        game.iconBroken = false
        if (res.exe_uri) game.exe_uri = res.exe_uri
      }
    } catch {}
  }
  if (need.length) saveGames()
}

onMounted(() => {
  loadGames()
  setContext(window.appContext || {})
  window.addEventListener('rpgrtl-context', onContext)
  window.addEventListener('rpgrtl-project-scanned', onProjectScannedEvent)
  setTimeout(() => { verifyGameLibrary() }, 320)
  setTimeout(() => { refreshMissingIcons() }, 600)
})
onBeforeUnmount(() => {
  window.removeEventListener('rpgrtl-context', onContext)
  window.removeEventListener('rpgrtl-project-scanned', onProjectScannedEvent)
})
</script>

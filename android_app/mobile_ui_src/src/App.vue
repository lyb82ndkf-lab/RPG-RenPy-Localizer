<template>
  <div class="app-container" :class="{ landscape: isLandscape, portrait: !isLandscape, 'game-tool-mode': inGameToolMode }">
    <section v-if="inGameToolMode" class="game-strip">
      <div class="game-strip-title"><span>游戏工具</span><strong>{{ gameTitle }}</strong></div>
      <nav class="game-tool-nav" aria-label="游戏工具导航">
        <router-link v-for="item in gameNavItems" :key="item.to" :to="item.to">{{ item.label }}</router-link>
      </nav>
    </section>

    <div v-if="shellStatus.visible" class="shell-status" :class="shellStatus.type">
      <span v-if="shellStatus.busy" class="mini-spinner"></span><span>{{ shellStatus.message }}</span>
    </div>

    <main class="view-content">
      <router-view v-slot="{ Component }"><component :is="Component" /></router-view>
    </main>

    <div v-if="launchOverlayVisible" class="launch-overlay" role="status" aria-live="polite">
      <div class="launch-card"><span class="launch-spinner"></span><strong>{{ shellStatus.title }}</strong><p>{{ shellStatus.message }}</p></div>
    </div>

    <nav v-if="!inGameToolMode" class="bottom-nav" :aria-label="t.mainNav">
      <router-link v-for="item in workspaceNavItems" :key="item.to" :to="item.to" class="nav-item">
        <svg class="nav-icon" aria-hidden="true"><use :href="iconHref(item.icon)"></use></svg><span>{{ item.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'

const t = { mainNav: '主导航', starting: '启动中', error: '需要处理', updated: '状态更新', ready: '就绪' }
const router = useRouter()
let statusTimer = null
const viewport = reactive({ width: window.innerWidth || 0, height: window.innerHeight || 0 })
const appContext = reactive({})
const shellStatus = reactive({ visible: false, busy: false, type: 'info', title: t.ready, message: '' })
const gameOnlyRoutes = new Set(['/data', '/saves', '/maps', '/controls', '/cheats'])
const workspaceNavItems = [
  { to: '/library', label: '游戏库', icon: 'rpgrtl-gamepad' },
  { to: '/translations', label: '翻译', icon: 'rpgrtl-translate' },
  { to: '/settings', label: '设置', icon: 'rpgrtl-settings' }
]
const gameNavItems = [
  { to: '/data', label: '数据' },
  { to: '/cheats', label: '实时' },
  { to: '/saves', label: '存档' },
  { to: '/maps', label: '地图' },
  { to: '/controls', label: '触控' }
]
const isLandscape = computed(() => viewport.width > viewport.height)
const hasRunningGame = computed(() => Boolean(appContext.has_game || appContext.game_mode === 'in_game' || appContext.mode === 'game'))
const inGameToolMode = computed(() => appContext.mode === 'game' || appContext.game_mode === 'in_game')
const gameTitle = computed(() => appContext.game_title || appContext.title || appContext.name || '已启动游戏')
const busyPatterns = ['launching','opening rpg maker','opening game','restoring game','启动游戏','进入游戏','打开游戏']
const donePatterns = ['ready','opened','enabled','found','done','完成','已打开','已启动','已选择','已加入']
const errorPatterns = ['failed','error','cannot','not found','失败','错误','异常','无法']
function iconHref(id) { return 'icons.svg#' + id }
const launchOverlayVisible = computed(() => shellStatus.busy && busyPatterns.some((item) => String(shellStatus.message || '').toLowerCase().includes(item.toLowerCase())))
function refreshViewport() { viewport.width = window.innerWidth || document.documentElement.clientWidth || 0; viewport.height = window.innerHeight || document.documentElement.clientHeight || 0 }
function enforceRoute() {
  const path = router.currentRoute.value.path
  if (!hasRunningGame.value && gameOnlyRoutes.has(path)) router.replace('/library')
  else if (inGameToolMode.value && !gameOnlyRoutes.has(path)) router.replace('/data')
}
function updateContext(ctx = {}) {
  Object.keys(appContext).forEach((k) => delete appContext[k])
  Object.assign(appContext, ctx || {})
  window.appContext = ctx || {}
  enforceRoute()
}
function sanitizeShellMessage(message) { return String(message || '').replace(/MTool/gi, 'RPGRenPyLocalizer').replace(/Discord/gi, '反馈渠道').replace(/Click To Exit/gi, '返回工具页') }
function setShellStatus(message, options = {}) {
  if (!message) return
  const lower = String(message).toLowerCase()
  const isError = options.type === 'error' || errorPatterns.some((item) => lower.includes(item))
  const busy = options.busy ?? (!isError && busyPatterns.some((item) => lower.includes(item)) && !donePatterns.some((item) => lower.includes(item)))
  shellStatus.visible = true; shellStatus.busy = busy; shellStatus.type = isError ? 'error' : busy ? 'busy' : 'success'; shellStatus.title = busy ? t.starting : isError ? t.error : t.updated; shellStatus.message = sanitizeShellMessage(message)
  window.dispatchEvent(new CustomEvent('rpgrtl-shell-message', { detail: { ...shellStatus } }))
  clearTimeout(statusTimer); statusTimer = setTimeout(() => { shellStatus.visible = false; if (!shellStatus.busy) shellStatus.message = '' }, busy ? 15000 : 4500)
}
function closeToolPage() { if (window.RPGRenPyShell?.toggleToolPage) window.RPGRenPyShell.toggleToolPage(); else setShellStatus('预览模式：真机会返回游戏画面') }

onMounted(() => {
  refreshViewport(); window.addEventListener('resize', refreshViewport); window.addEventListener('orientationchange', refreshViewport)
  updateContext(window.appContext || {})
  window.onAndroidToolMode = (ctx) => { updateContext(ctx); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })) }
  window.onAndroidExternalLaunchContext = (ctx) => { updateContext(ctx); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })) }
  window.onAndroidOpenToolPage = (targetPage) => { if (targetPage?.startsWith('/')) router.replace(targetPage) }
  window.onAndroidGameFolderPicked = (uri) => { const ctx = { uri, path: uri, name: '已选择游戏目录', engine: '扫描中' }; updateContext(ctx); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })); setShellStatus('已选择游戏目录', { busy: false }) }
  window.onAndroidGameExePicked = (uri) => { const ctx = { uri, path: uri, name: '已选择 EXE', engine: 'Windows exe / Wine backend', backend: 'wine' }; updateContext(ctx); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })) }
  window.onAndroidProjectScanned = (payload) => { let ctx = {}; try { ctx = typeof payload === 'string' ? JSON.parse(payload) : (payload || {}) } catch { ctx = { ok:false, error:String(payload||'scan parse error') } }; updateContext({ ...appContext, ...ctx }); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })); window.dispatchEvent(new CustomEvent('rpgrtl-project-scanned', { detail: ctx })) }
  window.onAndroidShellMessage = (message) => setShellStatus(message)
  window.onAndroidShellStatus = (message) => setShellStatus(message)
  enforceRoute()
})
watch([() => router.currentRoute.value.path, hasRunningGame, inGameToolMode], enforceRoute)
onBeforeUnmount(() => { clearTimeout(statusTimer); window.removeEventListener('resize', refreshViewport); window.removeEventListener('orientationchange', refreshViewport) })
</script>

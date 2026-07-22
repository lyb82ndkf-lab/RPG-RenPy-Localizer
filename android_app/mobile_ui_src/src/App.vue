<template>
  <div class="app-container" :class="{ landscape: isLandscape, portrait: !isLandscape, 'game-tool-mode': inGameToolMode }">
    <header class="top-bar">
      <div class="brand-block">
        <span class="brand-mark"><svg><use :href="iconHref('rpgrtl-gamepad')"></use></svg></span>
        <div class="brand-copy"><h1>RPGRenPyLocalizer</h1><p>{{ headerSubtitle }}</p></div>
      </div>
      <button v-if="hasRunningGame" class="close-btn" :aria-label="t.backGame" @click="closeToolPage">{{ inGameToolMode ? t.backGameShort : '?' }}</button>
    </header>

    <section class="dashboard-strip" v-if="!inGameToolMode">
      <div class="dash-item"><span>{{ t.currentGame }}</span><strong>{{ gameTitle }}</strong></div>
      <div class="dash-item"><span>{{ t.engine }}</span><strong>{{ gameEngine }}</strong></div>
      <div class="dash-item"><span>{{ t.status }}</span><strong :class="shellStatus.type">{{ shellStatus.visible ? shellStatus.title : t.ready }}</strong></div>
    </section>

    <section class="game-strip" v-else>
      <div><span>{{ t.gamePanel }}</span><strong>{{ gameTitle }}</strong></div>
      <button class="btn-ghost" @click="closeToolPage">{{ t.backGame }}</button>
    </section>

    <div v-if="shellStatus.visible" class="shell-status" :class="shellStatus.type">
      <span v-if="shellStatus.busy" class="mini-spinner"></span><span>{{ shellStatus.message }}</span>
    </div>

    <main class="view-content">
      <router-view v-slot="{ Component }"><transition name="fade" mode="out-in"><component :is="Component" /></transition></router-view>
    </main>

    <div v-if="shellStatus.busy" class="launch-overlay" role="status" aria-live="polite">
      <div class="launch-card"><span class="launch-spinner"></span><strong>{{ shellStatus.title }}</strong><p>{{ shellStatus.message }}</p></div>
    </div>

    <nav v-if="!inGameToolMode" class="bottom-nav" :aria-label="t.mainNav">
      <router-link v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item">
        <svg class="nav-icon" aria-hidden="true"><use :href="iconHref(item.icon)"></use></svg><span>{{ item.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'

const t = {
  subtitle: '\u7ad6\u5c4f\u5de5\u4f5c\u53f0', backGame: '\u8fd4\u56de\u6e38\u620f', backGameShort: '\u8fd4\u56de', currentGame: '\u5f53\u524d\u6e38\u620f', engine: '\u5f15\u64ce', status: '\u72b6\u6001', ready: '\u5c31\u7eea', mainNav: '\u4e3b\u5bfc\u822a',
  library: '\u6e38\u620f', translate: '\u7ffb\u8bd1', data: '\u6570\u636e', settings: '\u8bbe\u7f6e', starting: '\u6e38\u620f\u51c6\u5907\u4e2d', error: '\u9700\u8981\u5904\u7406', updated: '\u72b6\u6001\u66f4\u65b0', unknown: '\u672a\u77e5', none: '\u672a\u9009\u62e9', gamePanel: '\u6e38\u620f\u5185\u6570\u636e\u9762\u677f'
}
const router = useRouter()
let statusTimer = null
const viewport = reactive({ width: window.innerWidth || 0, height: window.innerHeight || 0 })
const appContext = reactive({})
const shellStatus = reactive({ visible: false, busy: false, type: 'info', title: t.ready, message: '' })
const navItems = [
  { to: '/library', label: t.library, icon: 'rpgrtl-gamepad' },
  { to: '/translations', label: t.translate, icon: 'rpgrtl-translate' },
  { to: '/cheats', label: t.data, icon: 'rpgrtl-database' },
  { to: '/settings', label: t.settings, icon: 'rpgrtl-settings' }
]
const isLandscape = computed(() => viewport.width > viewport.height)
const hasRunningGame = computed(() => Boolean(appContext.has_game || appContext.game_mode === 'in_game' || appContext.mode === 'game'))
const inGameToolMode = computed(() => isLandscape.value && hasRunningGame.value)
const headerSubtitle = computed(() => inGameToolMode.value ? t.gamePanel : (shellStatus.message || t.subtitle))
const gameTitle = computed(() => appContext.game_title || appContext.title || appContext.name || t.none)
const gameEngine = computed(() => appContext.engine || appContext.backend || t.unknown)
const busyPatterns = ['checking','scanning','preparing','launching','loading','starting','scan','import','open','\u542f\u52a8','\u626b\u63cf','\u51c6\u5907','\u5bfc\u5165']
const donePatterns = ['ready','opened','enabled','found','done','\u5b8c\u6210','\u5df2\u6253\u5f00','\u5df2\u542f\u52a8']
const errorPatterns = ['failed','error','cannot','not found','\u5931\u8d25','\u9519\u8bef','\u5f02\u5e38','\u65e0\u6cd5']
function iconHref(id) { return 'icons.svg#' + id }
function refreshViewport() { viewport.width = window.innerWidth || document.documentElement.clientWidth || 0; viewport.height = window.innerHeight || document.documentElement.clientHeight || 0 }
function updateContext(ctx = {}) { Object.keys(appContext).forEach((k) => delete appContext[k]); Object.assign(appContext, ctx || {}); window.appContext = ctx || {}; if ((ctx?.game_mode === 'in_game' || ctx?.mode === 'game') && router.currentRoute.value.path !== '/cheats') router.replace('/cheats') }
function sanitizeShellMessage(message) { return String(message || '').replace(/MTool/gi, 'RPGRenPyLocalizer').replace(/Discord/gi, '\u53cd\u9988\u6e20\u9053').replace(/Click To Exit/gi, '\u8fd4\u56de\u5de5\u5177\u9875') }
function setShellStatus(message, options = {}) {
  if (!message) return
  const lower = String(message).toLowerCase()
  const isError = options.type === 'error' || errorPatterns.some((item) => lower.includes(item))
  const busy = options.busy ?? (!isError && busyPatterns.some((item) => lower.includes(item)) && !donePatterns.some((item) => lower.includes(item)))
  shellStatus.visible = true; shellStatus.busy = busy; shellStatus.type = isError ? 'error' : busy ? 'busy' : 'success'; shellStatus.title = busy ? t.starting : isError ? t.error : t.updated; shellStatus.message = sanitizeShellMessage(message)
  window.dispatchEvent(new CustomEvent('rpgrtl-shell-message', { detail: { ...shellStatus } }))
  clearTimeout(statusTimer); statusTimer = setTimeout(() => { shellStatus.visible = false; if (!shellStatus.busy) shellStatus.message = '' }, busy ? 15000 : 4500)
}
function closeToolPage() { if (window.RPGRenPyShell?.toggleToolPage) window.RPGRenPyShell.toggleToolPage(); else setShellStatus('\u9884\u89c8\u6a21\u5f0f\uff1a\u771f\u673a\u5185\u4f1a\u8fd4\u56de\u6e38\u620f\u753b\u9762') }
onMounted(() => {
  refreshViewport(); window.addEventListener('resize', refreshViewport); window.addEventListener('orientationchange', refreshViewport)
  updateContext(window.appContext || {})
  window.onAndroidToolMode = (ctx) => { updateContext(ctx); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })) }
  window.onAndroidExternalLaunchContext = (ctx) => { updateContext(ctx); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })) }
  window.onAndroidOpenToolPage = (targetPage) => { if (targetPage?.startsWith('/')) router.replace(targetPage) }
  window.onAndroidGameFolderPicked = (uri) => { const ctx = { uri, path: uri, name: '\u5df2\u9009\u62e9\u6e38\u620f\u76ee\u5f55', engine: '\u626b\u63cf\u4e2d' }; updateContext(ctx); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })); setShellStatus('\u5df2\u9009\u62e9\u6e38\u620f\u76ee\u5f55\uff0c\u6b63\u5728\u626b\u63cf\u8d44\u6e90', { busy: true }) }
  window.onAndroidGameExePicked = (uri) => { const ctx = { uri, path: uri, name: '\u5df2\u9009\u62e9 EXE', engine: 'Windows exe / compatible runner' }; updateContext(ctx); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })) }
  window.onAndroidProjectScanned = (payload) => { const ctx = typeof payload === 'string' ? JSON.parse(payload) : payload; updateContext({ ...appContext, ...ctx }); window.dispatchEvent(new CustomEvent('rpgrtl-context', { detail: ctx })) }
  window.onAndroidShellMessage = (message) => setShellStatus(message)
  window.onAndroidShellStatus = (message) => setShellStatus(message)
})
onBeforeUnmount(() => { clearTimeout(statusTimer); window.removeEventListener('resize', refreshViewport); window.removeEventListener('orientationchange', refreshViewport) })
</script>

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as projectApi from '@/api/project'
import { isAndroidShell, launchShellGame, selectShellGamePath } from '@/utils/shell-bridge'

export const useProjectStore = defineStore('project', () => {
  const path = ref('')
  const engine = ref('')
  const summary = ref<Record<string, any>>({})
  const library = ref<any[]>([])
  const loading = ref(false)
  const launchContext = ref<Record<string, any>>({})
  const loaded = computed(() => Boolean(path.value))
  const launchBackend = computed(() => inferLaunchBackend(engine.value, summary.value))

  function inferLaunchBackend(engineValue: string, summaryValue: Record<string, any> = {}) {
    const engineText = `${engineValue || ''} ${summaryValue.engine || ''}`.toLowerCase()
    const backendText = String(summaryValue.backend || '').toLowerCase()
    if (engineText.includes('rpg maker')) return 'rpgmaker-webview'
    if (engineText.includes('ren')) return 'renpy'
    if (backendText === 'wine' || engineText.includes('windows exe') || engineText.includes('wine')) return 'wine'
    return 'rpgmaker-webview'
  }

  function clearFeatureCaches() {
    uni.$emit('rpgtl:project-changed')
  }

  function restoreLibrary() {
    library.value = uni.getStorageSync('game_library') || []
  }

  function restoreCurrentSelection() {
    const current = uni.getStorageSync('game_current')
    if (!current?.path) return
    path.value = current.path
    engine.value = current.engine || ''
    summary.value = current.summary || {}
    launchContext.value = current.launchContext || {}
  }

  function persistCurrentSelection(extra: Record<string, any> = {}) {
    if (!path.value) return
    uni.setStorageSync('game_current', {
      path: path.value,
      engine: engine.value,
      summary: summary.value,
      launchContext: launchContext.value,
      ...extra,
    })
  }

  function fallbackName(pathValue: string) {
    return decodeURIComponent(String(pathValue || '').split(/[\\/%]/).filter(Boolean).pop() || '未命名游戏')
  }

  function remember(game: any) {
    if (!game?.path && !game?.root) return
    const pathValue = game.path || game.root
    const existing = library.value.find((old) => old.path === pathValue)
    const cleanName = game.title || game.name || existing?.title || existing?.name || game.summary?.name || fallbackName(pathValue)
    const item = {
      ...existing,
      ...game,
      path: pathValue,
      title: cleanName,
      name: cleanName,
      time: Date.now(),
    }
    library.value = [item, ...library.value.filter((old) => old.path !== item.path)].slice(0, 50)
    uni.setStorageSync('game_library', library.value)
    if (path.value === item.path) persistCurrentSelection()
  }

  function rename(game: any, title: string) {
    if (!game?.path || !title.trim()) return
    library.value = library.value.map((item) => (
      item.path === game.path ? { ...item, title: title.trim(), name: title.trim() } : item
    ))
    uni.setStorageSync('game_library', library.value)
  }

  function remove(game: any) {
    if (!game?.path) return
    library.value = library.value.filter((item) => item.path !== game.path)
    uni.setStorageSync('game_library', library.value)
    if (path.value === game.path) {
      path.value = ''
      engine.value = ''
      summary.value = {}
      launchContext.value = {}
      uni.removeStorageSync('game_current')
    }
  }

  async function load(targetPath: string) {
    loading.value = true
    try {
      const result = await projectApi.loadProject(targetPath)
      path.value = result.project.root
      engine.value = result.project.engine
      summary.value = result.summary || {}
      const scannedName = summary.value.name || fallbackName(path.value)
      remember({
        path: path.value,
        engine: engine.value,
        name: scannedName,
        title: scannedName,
        backend: summary.value.backend,
        summary: summary.value,
      })
      persistCurrentSelection()
      clearFeatureCaches()
    } finally {
      loading.value = false
    }
  }

  function applyExternalLaunchContext(payload: Record<string, any>) {
    launchContext.value = payload || {}
    const title = payload?.game_title || payload?.container_name || '兼容运行器游戏'
    const syntheticPath = `compatible://${payload?.container_id ?? 'container'}/${encodeURIComponent(String(title))}`
    remember({
      path: syntheticPath,
      title,
      name: title,
      engine: 'Windows exe / Wine backend',
      summary: payload,
    })
    summary.value = { ...summary.value, ...payload }
    path.value = syntheticPath
    engine.value = 'Windows exe / Wine backend'
    persistCurrentSelection()
  }

  async function launch(game?: any) {
    const target = game || { path: path.value, engine: engine.value }
    if (target.path) {
      path.value = target.path
      engine.value = target.engine || engine.value
      if (isAndroidShell()) selectShellGamePath(target.path)
      persistCurrentSelection()
      clearFeatureCaches()
    }
    if (isAndroidShell()) {
      const backend = target.backend || inferLaunchBackend(target.engine || engine.value, target.summary || summary.value)
      launchShellGame(backend)
      uni.showToast({ title: '正在启动游戏', icon: 'none' })
      return
    }
    uni.showToast({ title: '请在 Android 壳内启动游戏', icon: 'none' })
  }

  return {
    path,
    engine,
    summary,
    library,
    loading,
    loaded,
    launchBackend,
    launchContext,
    restoreLibrary,
    restoreCurrentSelection,
    remember,
    rename,
    remove,
    load,
    launch,
    applyExternalLaunchContext,
  }
})

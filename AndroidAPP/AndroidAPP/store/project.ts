import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as projectApi from '@/api/project'
import { isAndroidShell, launchShellGame, selectShellGameFolder } from '@/utils/shell-bridge'

export const useProjectStore = defineStore('project', () => {
  const path = ref('')
  const engine = ref('')
  const summary = ref<Record<string, any>>({})
  const library = ref<any[]>([])
  const loading = ref(false)
  const loaded = computed(() => Boolean(path.value))

  function restoreLibrary() {
    library.value = uni.getStorageSync('game_library') || []
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
      remember({ path: path.value, engine: engine.value, name: scannedName, title: scannedName, summary: summary.value })
    } finally {
      loading.value = false
    }
  }

  async function launch(game?: any) {
    const target = game || { path: path.value, engine: engine.value }
    if (target.path) {
      path.value = target.path
      engine.value = target.engine || engine.value
      if (isAndroidShell()) selectShellGameFolder(target.path)
    }
    if (isAndroidShell()) {
      launchShellGame(target.engine || engine.value)
      uni.showToast({ title: '正在启动游戏', icon: 'none' })
      return
    }
    uni.showToast({ title: '请在 Android 壳内启动游戏', icon: 'none' })
  }

  return { path, engine, summary, library, loading, loaded, restoreLibrary, remember, rename, remove, load, launch }
})

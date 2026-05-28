import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as savesApi from '@/api/saves'

export const useSavesStore = defineStore('saves', () => {
  const slots = ref<savesApi.SaveSlot[]>([])
  const backups = ref<Record<string, any>[]>([])
  const loading = ref(false)
  const error = ref('')
  const savePath = ref('')
  const wineMode = ref(false)
  const slotsLoaded = ref(false)
  const backupsLoaded = ref(false)

  async function load(forceRefresh = false) {
    if (slotsLoaded.value && !forceRefresh) return
    loading.value = true
    error.value = ''
    try {
      const result = await savesApi.listSaveSlots()
      slots.value = result.slots || []
      savePath.value = result.save_path || ''
      wineMode.value = Boolean(result.wine)
      slotsLoaded.value = true
    } catch (err: any) {
      error.value = err?.message || String(err)
      slots.value = []
    } finally {
      loading.value = false
    }
  }

  async function backup() {
    const result = await savesApi.createBackup()
    await loadBackups(true)
    return result.message
  }

  async function loadBackups(forceRefresh = false) {
    if (backupsLoaded.value && !forceRefresh) return
    const result = await savesApi.listBackups()
    backups.value = result.backups || []
    backupsLoaded.value = true
  }

  async function refreshSavePath() {
    try {
      const result = await savesApi.getSavePath()
      savePath.value = result.savePath || ''
      wineMode.value = Boolean(result.wine)
      return result
    } catch (err: any) {
      savePath.value = ''
      return { savePath: '', exists: false }
    }
  }

  function reset() {
    slots.value = []
    backups.value = []
    error.value = ''
    savePath.value = ''
    wineMode.value = false
    slotsLoaded.value = false
    backupsLoaded.value = false
  }

  uni.$on('rpgtl:project-changed', reset)

  return { slots, backups, loading, error, savePath, wineMode, load, backup, loadBackups, refreshSavePath, reset }
})

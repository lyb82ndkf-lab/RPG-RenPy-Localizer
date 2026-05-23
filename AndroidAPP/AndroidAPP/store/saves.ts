import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as savesApi from '@/api/saves'

export const useSavesStore = defineStore('saves', () => {
  const slots = ref<savesApi.SaveSlot[]>([])
  const backups = ref<Record<string, any>[]>([])
  const loading = ref(false)
  const slotsLoaded = ref(false)
  const backupsLoaded = ref(false)

  async function load(forceRefresh = false) {
    if (slotsLoaded.value && !forceRefresh) return
    loading.value = true
    try {
      const result = await savesApi.listSaveSlots()
      slots.value = result.slots || []
      slotsLoaded.value = true
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

  return { slots, backups, loading, load, backup, loadBackups }
})

import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as mapsApi from '@/api/maps'

export const useMapsStore = defineStore('maps', () => {
  const maps = ref<mapsApi.MapInfo[]>([])
  const detail = ref<Record<string, any> | null>(null)
  const detailCache = ref<Record<string, Record<string, any>>>({})
  const loading = ref(false)
  const loaded = ref(false)

  async function load(forceRefresh = false) {
    if (loaded.value && !forceRefresh) return
    loading.value = true
    try {
      const result = await mapsApi.listMaps()
      maps.value = result.maps || []
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  async function open(id: number) {
    if (detailCache.value[id]) {
      detail.value = detailCache.value[id]
      return
    }
    const result = await mapsApi.mapDetail(id)
    detail.value = result.detail
    if (detail.value) detailCache.value = { ...detailCache.value, [id]: detail.value }
  }

  return { maps, detail, loading, load, open }
})

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as dataApi from '@/api/data'

export const useDataStore = defineStore('data', () => {
  const category = ref('Actors.json')
  const records = ref<dataApi.DataRecord[]>([])
  const selectedKey = ref('')
  const loading = ref(false)
  const cache = ref<Record<string, dataApi.DataRecord[]>>({})

  const groups = computed(() => {
    const map = new Map<string, { label: string; records: dataApi.DataRecord[] }>()
    records.value.forEach((record, index) => {
      const key = record.object_id || `${record.file}:${index}`
      if (!map.has(key)) map.set(key, { label: record.object_label || record.file || '对象', records: [] })
      map.get(key)!.records.push(record)
    })
    return Array.from(map.entries()).map(([key, value]) => ({ key, ...value }))
  })

  const selected = computed(() => {
    if (!selectedKey.value) return null
    return groups.value.find((item) => item.key === selectedKey.value) || null
  })

  async function load(forceRefresh = false) {
    if (!forceRefresh && cache.value[category.value]) {
      records.value = cache.value[category.value]
      return
    }
    loading.value = true
    try {
      const result = await dataApi.listRecords(category.value, 5000)
      records.value = result.records || []
      cache.value = { ...cache.value, [category.value]: records.value }
      selectedKey.value = ''
    } finally {
      loading.value = false
    }
  }

  function reset() {
    records.value = []
    selectedKey.value = ''
    cache.value = {}
  }

  uni.$on('rpgtl:project-changed', reset)

  return { category, records, selectedKey, loading, groups, selected, load, reset }
})

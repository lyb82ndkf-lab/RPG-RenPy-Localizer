import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as translateApi from '@/api/translate'

export const useTranslationStore = defineStore('translation', () => {
  const entries = ref<translateApi.TranslationEntry[]>([])
  const status = ref<'all' | 'untranslated' | 'translated'>('untranslated')
  const range = ref<'dialogue' | 'database'>('dialogue')
  const query = ref('')
  const loading = ref(false)
  const loaded = ref(false)

  const filtered = computed(() => entries.value.filter((entry) => {
    const translated = Boolean(String(entry.target || '').trim())
    const category = String(entry.category || '').toLowerCase()
    if (range.value === 'dialogue' && category !== 'dialogue') return false
    if (range.value === 'database' && category !== 'database') return false
    if (status.value === 'untranslated' && translated) return false
    if (status.value === 'translated' && !translated) return false
    return !query.value || String(entry.source || '').includes(query.value)
  }))

  async function load(limit = 800, forceRefresh = false) {
    if (loaded.value && !forceRefresh) return
    loading.value = true
    try {
      const result = await translateApi.listEntries(limit)
      entries.value = result.entries || []
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  function updateTarget(id: string, target: string) {
    const item = entries.value.find((entry) => entry.entry_id === id)
    if (item) item.target = target
  }

  async function translateVisible(settings: Record<string, any>) {
    const targets = filtered.value.filter((entry) => !String(entry.target || '').trim()).slice(0, 160)
    if (!targets.length) return 0
    loading.value = true
    let done = 0
    try {
      for (let index = 0; index < targets.length; index += 20) {
        const chunk = targets.slice(index, index + 20)
        const result = await translateApi.aiTranslate(settings, chunk)
        ;(result.translations || []).forEach((item: any) => {
          const original = entries.value.find((entry) => entry.entry_id === item.entry_id || entry.source === item.source)
          if (original && item.target) original.target = item.target
        })
        done += chunk.length
        await new Promise((resolve) => setTimeout(resolve, 0))
      }
      return done
    } finally {
      loading.value = false
    }
  }

  return { entries, status, range, query, loading, filtered, load, updateTarget, translateVisible }
})

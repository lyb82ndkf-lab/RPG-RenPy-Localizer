import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as translateApi from '@/api/translate'

export const useTranslationStore = defineStore('translation', () => {
  const entries = ref<translateApi.TranslationEntry[]>([])
  const status = ref<'all' | 'untranslated' | 'translated'>('all')
  const range = ref<'all' | 'dialogue' | 'database'>('all')
  const query = ref('')
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')
  const doneCount = ref(0)
  const totalCount = ref(0)
  const progress = computed(() => totalCount.value > 0 ? Math.round(doneCount.value / totalCount.value * 100) : 0)

  const filtered = computed(() => entries.value.filter((entry) => {
    const translated = Boolean(String(entry.target || '').trim())
    const category = String(entry.category || '').toLowerCase()
    if (range.value === 'all') {
      // no category filter
    } else
    if (range.value === 'dialogue' && category !== 'dialogue') return false
    if (range.value === 'database' && category !== 'database') return false
    if (status.value === 'untranslated' && translated) return false
    if (status.value === 'translated' && !translated) return false
    return !query.value || String(entry.source || '').includes(query.value)
  }))

  async function load(limit = 5000, forceRefresh = false) {
    if (loaded.value && !forceRefresh) return
    loading.value = true
    error.value = ''
    try {
      const result = await translateApi.listEntries(limit)
      entries.value = result.entries || []
      loaded.value = true
    } catch (err: any) {
      error.value = err?.message || 'Load translation entries failed.'
      throw err
    } finally {
      loading.value = false
    }
  }

  function updateTarget(id: string, target: string) {
    const item = entries.value.find((entry) => entry.entry_id === id)
    if (item) item.target = target
  }

  async function translateVisible(settings: Record<string, any>) {
    const targets = filtered.value.filter((entry) => !String(entry.target || '').trim())
    if (!targets.length) return 0
    loading.value = true
    error.value = ''
    doneCount.value = 0
    totalCount.value = targets.length
    let done = 0
    try {
      for (let index = 0; index < targets.length; index += 50) {
        const chunk = targets.slice(index, index + 50)
        const result = await translateApi.aiTranslate(settings, chunk)
        if ((result as any)?.ok === false || (result as any)?.error) {
          throw new Error((result as any).error || 'AI translate failed.')
        }
        ;(result.translations || []).forEach((item: any, itemIndex: number) => {
          const original = entries.value.find((entry) => entry.entry_id === item.entry_id || entry.source === item.source)
            || chunk.find((entry) => entry.entry_id === item.entry_id || entry.source === item.source)
            || chunk[Number(item.entry_id) - 1]
            || chunk[Number(item.index)]
            || chunk[itemIndex]
          if (original && item.target) original.target = item.target
        })
        done += chunk.length
        doneCount.value = done
        await new Promise((resolve) => setTimeout(resolve, 0))
      }
      return done
    } catch (err: any) {
      error.value = err?.message || 'AI translate failed.'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function saveTranslated(mode = 'embed') {
    const translated = entries.value.filter((entry) => String(entry.target || '').trim())
    if (!translated.length) return 0
    loading.value = true
    error.value = ''
    try {
      const result = await translateApi.saveEntries(translated, mode)
      return result.count || translated.length
    } catch (err: any) {
      error.value = err?.message || 'Save translation failed.'
      throw err
    } finally {
      loading.value = false
    }
  }

  function reset() {
    entries.value = []
    loaded.value = false
    error.value = ''
    doneCount.value = 0
    totalCount.value = 0
  }

  uni.$on('rpgtl:project-changed', reset)

  return { entries, status, range, query, loading, loaded, error, doneCount, totalCount, progress, filtered, load, updateTarget, translateVisible, saveTranslated, reset }
})

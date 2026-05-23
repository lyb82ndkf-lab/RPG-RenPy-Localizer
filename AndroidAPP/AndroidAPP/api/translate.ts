import { request } from './index'
import { isAndroidShell, shellJson } from '@/utils/shell-bridge'

export interface TranslationEntry {
  entry_id: string
  source: string
  target?: string
  file?: string
  context?: string
  category?: string
}

export function listEntries(limit = 500) {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ entries: TranslationEntry[]; count: number }>('androidTranslationEntries', limit))
  return request<{ entries: TranslationEntry[]; count: number }>(`/api/translate/entries?limit=${limit}`)
}

export function aiTranslate(settings: Record<string, any>, entries: TranslationEntry[]) {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ translations: TranslationEntry[] }>('androidAiTranslate', JSON.stringify({ settings, entries })))
  return request<{ translations: TranslationEntry[] }>('/api/translate/ai', {
    method: 'POST',
    data: { settings, entries },
  })
}


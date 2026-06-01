import { request } from './index'
import { isAndroidShell, shellJson } from '@/utils/shell-bridge'

export interface SaveSlot {
  name: string
  slot_id?: number
  size?: number
  modified_at?: string
  path?: string
  source?: string
  save_root?: string
}

export function listSaveSlots() {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ slots: SaveSlot[]; save_path?: string; wine?: boolean }>('androidSaveSlots'))
  return request<{ slots: SaveSlot[] }>('/api/saves')
}

export function createBackup() {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ message: string }>('androidCreateSaveBackup'))
  return request<{ message: string }>('/api/saves/backup', { method: 'POST' })
}

export function listBackups() {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ backups: Record<string, any>[] }>('androidBackups'))
  return request<{ backups: Record<string, any>[] }>('/api/saves/backups')
}

export function getSavePath() {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ savePath: string; exists: boolean; wine?: boolean }>('androidGetSavePath'))
  return Promise.resolve({ savePath: '', exists: false })
}


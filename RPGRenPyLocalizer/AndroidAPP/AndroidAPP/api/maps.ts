import { request } from './index'
import { isAndroidShell, shellJson } from '@/utils/shell-bridge'

export interface MapInfo {
  map_id: number
  name: string
  width?: number
  height?: number
  event_count?: number
}

export function listMaps() {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ maps: MapInfo[] }>('androidMaps'))
  return request<{ maps: MapInfo[] }>('/api/maps')
}

export function mapDetail(id: number) {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ detail: Record<string, any> }>('androidMapDetail', id))
  return request<{ detail: Record<string, any> }>(`/api/maps/${id}`)
}


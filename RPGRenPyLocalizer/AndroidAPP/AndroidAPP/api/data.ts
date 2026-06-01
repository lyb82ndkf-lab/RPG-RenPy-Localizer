import { request } from './index'
import { isAndroidShell, shellJson } from '@/utils/shell-bridge'

export interface DataRecord {
  object_id?: string
  object_label?: string
  label?: string
  value?: string
  file?: string
  location?: string
}

export function listRecords(category = '', limit = 5000) {
  if (isAndroidShell()) {
    return Promise.resolve(shellJson<{ records: DataRecord[] }>('androidDataRecords', JSON.stringify({ category, limit })))
  }
  const query = category ? `&category=${encodeURIComponent(category)}` : ''
  return request<{ records: DataRecord[] }>(`/api/records?limit=${limit}${query}`)
}

export function updateRecord(record: DataRecord, value: string) {
  if (isAndroidShell()) return Promise.resolve(shellJson<{ value: string; message?: string }>('androidUpdateRecord', JSON.stringify(record), value))
  return request<{ value: string; message?: string }>('/api/records/update', {
    method: 'POST',
    data: { record, value },
  })
}


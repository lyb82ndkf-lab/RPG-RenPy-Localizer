import { request } from './index'
import { isAndroidShell, scanShellProject } from '@/utils/shell-bridge'

export interface ProjectInfo {
  root: string
  engine: string
  launcher_path?: string
  android_runtime_note?: string
}

export function loadProject(path: string) {
  if (isAndroidShell()) return scanShellProject(path)
  return request<{ project: ProjectInfo; summary: Record<string, any> }>('/api/project/load', {
    method: 'POST',
    data: { path },
  })
}

export function health() {
  return request<Record<string, any>>('/api/health')
}


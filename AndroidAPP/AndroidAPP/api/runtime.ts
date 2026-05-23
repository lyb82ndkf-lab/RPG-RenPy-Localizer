import { request } from './index'

export function runtimeStatus() {
  return request<Record<string, any>>('/api/runtime/status')
}

export function applyCheat(action: string, value?: unknown) {
  return request<Record<string, any>>('/api/runtime/cheat', {
    method: 'POST',
    data: { action, value },
  })
}


import { API_BASE } from '@/utils/constants'

type RequestOptions = UniApp.RequestOptions & { data?: unknown }

export function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE}${path}`,
      header: { 'Content-Type': 'application/json' },
      ...options,
      success: (res) => {
        const payload = res.data as any
        if (payload?.ok === false) {
          reject(new Error(payload.error || '请求失败'))
          return
        }
        const { ok, error, ...rest } = payload || {}
        resolve((payload?.data ?? rest) as T)
      },
      fail: reject,
    })
  })
}


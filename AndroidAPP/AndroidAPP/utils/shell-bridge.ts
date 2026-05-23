declare global {
  interface Window {
    RPGRenPyShell?: Record<string, (...args: any[]) => any>
    onAndroidGameFolderPicked?: (uri: string) => void
    onAndroidProjectScanned?: (payload: string | Record<string, any>) => void
    onAndroidShellMessage?: (message: string) => void
  }
}

export function isAndroidShell() {
  return typeof window !== 'undefined' && !!window.RPGRenPyShell
}

export function callShell(method: string, ...args: any[]) {
  const bridge = window.RPGRenPyShell
  if (!bridge || typeof bridge[method] !== 'function') {
    throw new Error('当前不在 Android 壳内运行。')
  }
  return bridge[method](...args)
}

export function shellJson<T = any>(method: string, ...args: any[]): T {
  const raw = callShell(method, ...args)
  const payload = typeof raw === 'string' ? JSON.parse(raw) : raw
  if (payload?.ok === false) throw new Error(payload.error || 'Android 壳调用失败')
  return payload as T
}

export function launchShellGame(engine = '') {
  if (!isAndroidShell()) return false
  const lower = String(engine || '').toLowerCase()
  if (lower.includes('ren')) {
    callShell('launchRenpyGame')
  } else if (lower.includes('exe') || lower.includes('windows')) {
    callShell('launchExeWithExternalRunner')
  } else {
    callShell('launchSelectedGame')
  }
  return true
}

export function selectShellGameFolder(path: string) {
  if (!isAndroidShell() || !path) return false
  shellJson('selectGameFolder', path)
  return true
}

export function pickShellFolder(): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!isAndroidShell()) {
      reject(new Error('当前不在 Android 壳内运行。'))
      return
    }
    const previous = window.onAndroidGameFolderPicked
    window.onAndroidGameFolderPicked = (uri: string) => {
      previous?.(uri)
      resolve(uri)
    }
    callShell('pickGameFolder')
  })
}

export function scanShellProject(): Promise<{ project: any; summary: Record<string, any> }> {
  return new Promise((resolve, reject) => {
    if (!isAndroidShell()) {
      reject(new Error('当前不在 Android 壳内运行。'))
      return
    }
    const previousScan = window.onAndroidProjectScanned
    const previousMessage = window.onAndroidShellMessage
    window.onAndroidProjectScanned = (payload: string | Record<string, any>) => {
      previousScan?.(payload)
      const summary = typeof payload === 'string' ? JSON.parse(payload) : payload
      resolve({
        project: {
          root: summary.uri || summary.root || '',
          engine: summary.engine || '未知',
        },
        summary,
      })
    }
    window.onAndroidShellMessage = (message: string) => {
      previousMessage?.(message)
      if (message.includes('失败')) reject(new Error(message))
    }
    callShell('scanSelectedGame')
  })
}

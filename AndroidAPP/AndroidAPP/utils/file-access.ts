import { isAndroidShell, pickShellFolder } from './shell-bridge'

export function pickGamePath(): Promise<string> {
  if (isAndroidShell()) return pickShellFolder()
  return new Promise((resolve) => {
    uni.chooseFile({
      count: 1,
      type: 'all',
      success: (res: any) => {
        const file = res.tempFiles?.[0]
        resolve(file?.path || file?.name || '')
      },
      fail: () => resolve(''),
    })
  })
}

export function openSettingsPage() {
  uni.navigateTo({ url: '/pages/settings/settings' })
}

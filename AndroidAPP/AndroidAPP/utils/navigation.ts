const PAGE_ROUTES: Record<string, string> = {
  index: '/pages/index/index',
  translate: '/pages/translate/translate',
  data: '/pages/data-editor/data-editor',
  runtime: '/pages/runtime/runtime',
  maps: '/pages/maps/maps',
  saves: '/pages/saves/saves',
  settings: '/pages/settings/settings',
}

export function switchTopPage(key: string) {
  if (key.endsWith?.('.json')) {
    const url = `/pages/data-editor/data-editor?category=${encodeURIComponent(key)}`
    uni.redirectTo({
      url,
      fail: () => uni.reLaunch({ url }),
    })
    return
  }
  const url = PAGE_ROUTES[key] || PAGE_ROUTES.index
  const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
  const current = pages.length ? `/${pages[pages.length - 1].route}` : ''
  if (current === url) return
  uni.redirectTo({
    url,
    fail: () => uni.reLaunch({ url }),
  })
}


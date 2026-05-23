import { DATA_CATEGORIES } from './constants'

export const TOP_NAV_ITEMS = [
  { path: 'index', label: '游戏库' },
  { path: 'runtime', label: '实时' },
  ...DATA_CATEGORIES.filter((item) => item.value).map((item) => ({ path: item.value, label: item.label })),
  { path: 'translate', label: '汉化' },
  { path: 'maps', label: '地图' },
  { path: 'saves', label: '存档' },
  { path: 'settings', label: '虚拟按键' },
]

export function isDataCategory(key: string) {
  return DATA_CATEGORIES.some((item) => item.value === key)
}

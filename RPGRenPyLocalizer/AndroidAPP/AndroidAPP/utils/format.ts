export function truncate(value: unknown, length = 60) {
  const text = String(value ?? '')
  return text.length > length ? `${text.slice(0, length)}...` : text
}

export function dateFormat(value: number | string | Date) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function safeArray<T>(value: T[] | undefined | null): T[] {
  return Array.isArray(value) ? value : []
}


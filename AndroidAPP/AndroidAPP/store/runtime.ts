import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as runtimeApi from '@/api/runtime'

export const useRuntimeStore = defineStore('runtime', () => {
  const connected = ref(false)
  const status = ref<Record<string, any>>({})

  async function refresh() {
    status.value = await runtimeApi.runtimeStatus()
    connected.value = true
  }

  async function cheat(action: string, value?: unknown) {
    const result = await runtimeApi.applyCheat(action, value)
    status.value = { ...status.value, ...result }
  }

  return { connected, status, refresh, cheat }
})


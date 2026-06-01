export const API_BASE = 'http://127.0.0.1:8765'

export const DATA_CATEGORIES = [
  { label: '角色', value: 'Actors.json' },
  { label: '物品', value: 'Items.json' },
  { label: '防具', value: 'Armors.json' },
  { label: '武器', value: 'Weapons.json' },
  { label: '职业', value: 'Classes.json' },
  { label: '状态', value: 'States.json' },
  { label: '全部', value: '' },
]

export const AI_PROVIDERS = [
  { label: 'DeepSeek', value: 'deepseek', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat' },
  { label: '豆包 Ark', value: 'doubao', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', model: 'doubao-seed-2-0-mini-250715' },
  { label: '智谱 GLM', value: 'glm', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  { label: 'NVIDIA', value: 'nvidia', baseUrl: '', model: 'minimaxai/minimax-m2.7' },
  { label: '小米 Token Plan', value: 'xiaomi_token_plan', baseUrl: 'https://token-plan-sgp.xiaomimimo.com/v1', model: 'mimo-v2.5' },
  { label: 'OpenAI 兼容', value: 'openai_compatible', baseUrl: '', model: 'gpt-4o-mini' },
]

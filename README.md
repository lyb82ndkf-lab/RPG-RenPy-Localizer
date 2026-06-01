# RPGRenPyLocalizer

**Windows PC 本地化工具**，面向 RPG Maker MV/MZ 和 Ren'Py 单机游戏。支持实时游戏翻译、文本提取与 AI 翻译、数据编辑、存档修改、实时控制。

---

## 核心功能：实时游戏翻译

这是本工具最大的特色 — 不用事先翻译所有文本，而是**运行时实时 hook 游戏文本、实时调用 AI 翻译、实时嵌入到游戏中**。

### 工作流

```
游戏渲染文本
     ↓
实时 hook 拦截（猴子补丁 / JS 注入）
     ↓
文本发送到本地桥接服务器
     ↓
桌面工具轮询获取 → 调用 AI/百度翻译
     ↓
翻译结果写回桥接翻译表
     ↓
游戏轮询拉取 → 替换当前对话/菜单文本
     ↓
（无感，游戏不重启、不 Reload）
```

### Ren'Py 实时翻译

通过 `zz_rpgrtl_live_bridge.rpy` 脚本在 Ren'Py 引擎内注入 **6 个猴子补丁**，拦截对话、菜单、Text widget 的渲染路径：

| 钩子 | 作用 |
|------|------|
| `ADVCharacter.__call__` | 追踪对话标识符与原文 |
| `ADVCharacter.prefix_suffix` | 对话显示前替换——**实时嵌入核心路径** |
| `ADVCharacter.do_display` | 最终渲染前替换，处理对话文本标签 |
| `Text.set_text` | 通用 Text widget 替换，支持强制注入 |
| `Text.render` | 最彻底的兜底替换 |
| `config.replace_text` | 全部文本渲染前替换 |

**操作步骤**：

1. 加载 Ren'Py 游戏 exe
2. 点击 **「实时游戏翻译」** 按钮
3. 工具自动：安装桥接脚本 → 启动游戏 → 启动本地 HTTP 服务器
4. 游戏中显示对话时，工具实时捕获并 AI 翻译
5. 翻译结果实时替换到游戏画面上 — **所见即所得，无需重启**

### RPG Maker MV/MZ 实时桥接

通过 `RPGRenPyBridge.js` 插件在 RPG Maker 的 NW.js/Electron 进程内启动 HTTP 服务器，直接读写游戏内存对象：

| 功能 | 说明 |
|------|------|
| 实时翻译注入 | 通过 `/translation` 接口注入翻译字典，替换对话框/菜单/位图文字 |
| 实时属性修改 | HP/MP/TP/金币/开关/变量/经验倍率 |
| 游戏加速 | 游戏速度 / 移动速度 / 战斗速度倍率 |
| 穿墙 / 上帝模式 / 自动战斗 | 进程内 JavaScript 补丁 |
| 地图点击瞬移 | 勾选后点击地图格子即可传送 |

---

## 功能总览

| 模块 | RPG Maker MV/MZ | Ren'Py |
|------|:--:|:--:|
| **实时游戏翻译** | ✅ JS 桥接注入 | ✅ 6 层猴子补丁 + HTTP 桥接 |
| 文本提取 | ✅ JSON / 地图事件 / 系统文本 | ✅ 编译脚本 / 运行时提取 |
| AI 翻译 | ✅ 7 个渠道，并行批量，缓存去重 | ✅ 同左 |
| 翻译工作台 | ✅ 提取/翻译/导入/导出/嵌入 | ✅ 同左 |
| 数据编辑器 | ✅ 物品/角色/职业/敌人/技能/状态 | — |
| 地图查看 | ✅ 瓦片地图 + 事件 + 坐标传送 | — |
| 存档修改 | ✅ 金币/物品/角色/开关/变量 | — |
| 实时作弊 | ✅ 穿墙/上帝/自动战斗/瞬移/加速 | — |

---

## AI 翻译渠道

| 渠道 | 说明 |
|------|------|
| OpenAI | 标准 API（自定义 Base URL） |
| DeepSeek | 高性价比大模型 |
| Doubao（豆包） | 字节跳动 |
| GLM | 智谱 AI |
| NVIDIA | NVIDIA AI |
| Xiaomi Token Plan | 小米 token 计划 / 普通 API Key |
| 百度翻译 API | 百度机器翻译 |

支持 **多厂商并行翻译**，自动按批次轮询分配到不同厂商，最大化翻译吞吐量。

---

## 界面说明

```
┌──────────────────────────────────────────────┐
│  导航栏          │  内容区                    │
│                   │                            │
│  游戏库           │  游戏库：已加入的项目列表    │
│  翻译工作台       │  翻译工作台：提取/翻译/导出  │
│  数据编辑器       │  数据编辑器：字段查看与编辑  │
│  存档修改         │  存档修改：金币/物品/角色    │
│  地图查看         │  地图查看：瓦片地图+事件     │
│  环境与备份       │  环境与备份：自动备份管理    │
│                   │                            │
└──────────────────────────────────────────────┘
```

- **翻译工作台**：左侧翻译列表 + 右侧译文编辑 + 底部 AI 设置
- **数据编辑器**：左侧对象列表 + 右侧属性编辑（双击值原地编辑）
- **存档修改**：左侧存档选择 + 右侧物品/角色/开关/变量多标签页
- **地图查看**：左侧瓦片地图 + 右侧事件列表与详情

---

## 安装与运行

### 使用发布版（推荐）

1. 下载 `dist\RPGRenPyLocalizer\` 整个文件夹
2. 双击 `RPGRenPyLocalizer.exe`
3. **不要只发单独 exe** — `_internal` 文件夹包含 Python 运行时，缺了无法启动

目标电脑不需要安装 Python。

### 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

---

## 使用流程

### 1. 加载游戏
- 点击「选择 exe」选择游戏启动文件
- 或直接拖入 exe 到窗口
- 工具自动识别引擎类型（RPG Maker MV/MZ / Ren'Py）

### 2. 实时游戏翻译（Ren'Py）
- 加载项目后，顶部标题栏会出现 **「实时游戏翻译」** 按钮
- 点击后工具自动安装桥接脚本 + 启动游戏 + 启动翻译服务器
- 游戏运行时，显示的文本自动捕获、翻译、替换
- 可在工具的翻译工作台中查看已捕获文本和翻译结果

### 3. 离线批量翻译
- 切换到「翻译工作台」
- 点击「提取文本」
- 选择翻译范围和文件
- 配置 AI 渠道和 API Key → 「保存设置」
- 点击「一键翻译全部」或「翻译选中」
- 支持导入/导出翻译包

### 4. 数据修改
- 切换到「数据编辑器」
- 选择分类（物品/角色/职业等）
- 选中对象 → 右侧双击值 → 修改 → 保存

### 5. 存档修改
- 切换到「存档修改」
- 点击「刷新存档列表」
- 选择存档 → 修改金币/物品/角色/开关/变量

### 6. 实时控制（RPG Maker）
- 点击「安装实时组件」→ 重启游戏 → 「连接实时游戏」
- 可使用：穿墙、上帝模式、自动战斗、地图点击瞬移、游戏加速

---

## 配置保存位置

| 内容 | 路径 |
|------|------|
| AI 配置 / API Key | `%APPDATA%\RPGRenPyLocalizer\settings.json` |
| 翻译记忆缓存 | `%APPDATA%\RPGRenPyLocalizer\translation_memory.json` |
| 项目级翻译缓存 | `<游戏目录>\.rpgrtl_workspace\` |
| 自动备份 | `<游戏目录>\.rpgrtl_backup\` |

AI 配置保存在当前 Windows 用户目录，**发给别人时不会泄露你的 API Key**。

---

## 实时翻译技术细节

### Ren'Py 桥接架构

```
桌面工具 (app.py)                    Ren'Py 游戏进程
┌──────────────────┐                ┌──────────────────────┐
│  AI 翻译引擎     │                │  zz_rpgrtl_live_bridge.rpy  │
│  (OpenAI/DeepSeek│                │                      │
│   /百度... )      │    HTTP :32180  │  ThreadingHTTPServer  │
│                  │◄──────────────►│  /pull → 翻译表       │
│  _renpy_realtime │                │  /translation → 单条  │
│  _worker (1.5s)  │                │  /notify → 刷新通知   │
│                  │                │  /seen → 记录已见文本  │
│  轮询 → 翻译     │                │                      │
│  → 写回 → 通知   │                │  猴子补丁 (6处):      │
│                  │                │  ADVCharacter.__call__│
│  每5s 持久化缓存  │                │  Text.set_text        │
│                  │                │  config.replace_text  │
└──────────────────┘                └──────────────────────┘
```

### RPG Maker MV/MZ 桥接架构

```
桌面工具                        RPG Maker (NW.js/Electron)
┌──────────────┐               ┌────────────────────────┐
│  HTTP 客户端  │   :32179      │  RPGRenPyBridge.js     │
│              │◄─────────────►│  HTTP 服务器 (Node.js)  │
│  /state      │               │                        │
│  /set        │               │  JS 补丁:               │
│  /translation│               │  Window_Base.convertEscapeCharacters │
└──────────────┘               │  Bitmap.drawText        │
                               │  Scene_Map.update       │
                               └────────────────────────┘
```

---

## 打包发布

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

打包结果：`dist\RPGRenPyLocalizer\`（包含 exe + _internal）

分享时把整个 `dist\RPGRenPyLocalizer\` 文件夹打包即可。

---

## 项目结构

```text
RPGRenPyLocalizer/
├── main.py                    # 入口
├── launcher.py                # 启动引导窗口
├── build_release.ps1          # PyInstaller 打包脚本
├── static/                    # 图标与静态资源
├── toolkit/                   # 核心工具包
│   ├── app.py                 # 主界面（~5800 行）
│   ├── detectors.py           # 游戏引擎检测
│   ├── models.py              # 数据模型
│   ├── renpy.py               # Ren'Py 服务（桥接 + 实时翻译）
│   ├── rpgmaker.py            # RPG Maker 服务（桥接 + 数据解析）
│   ├── storage.py             # JSON 持久化与翻译包
│   ├── ui_layout.py           # 响应式布局控制
│   ├── ui_theme.py            # ttk 主题
│   ├── workspace.py           # 工作空间与缓存管理
│   └── core/
│       ├── facade.py          # 无头核心（CLI/API 复用）
│       └── __main__.py
└── dist/                      # 打包输出
```

---

## 常见问题

### 为什么没有 Python 也能运行？
发布版用 PyInstaller 打包，`_internal` 自带 Python 运行时。

### 实时翻译会卡顿吗？
翻译在后台线程进行，游戏画面替换仅涉及字典查找（毫秒级），不会影响游戏帧率。

### 实时翻译支持哪些 AI 渠道？
所有 7 个渠道都支持。翻译结果即时写入桥接翻译表，游戏下一次渲染时自动生效。

### 为什么翻译会跳过一些文本？
工具自动过滤路径、乱码、系统占位文本和非对白内容。

### 地图瞬移没反应？
需要先安装实时组件 → 重启游戏 → 勾选「地图点击瞬移」→ 点击地图格子。

### API Key 保存在哪？安全吗？
保存在 `%APPDATA%\RPGRenPyLocalizer\settings.json`，仅当前 Windows 用户可访问。

### 支持哪些引擎版本？
- RPG Maker MV / MZ（完整支持）
- Ren'Py（完整支持：批量翻译 + 实时翻译）
- RPG Maker XP / VX / VX Ace（部分支持）

---

## 说明

本工具用于单机游戏汉化与实时翻译，不面向网络游戏，不用于联机作弊。

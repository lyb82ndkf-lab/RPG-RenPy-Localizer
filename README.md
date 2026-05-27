# RPGRenPyLocalizer

**Windows 本地化与实时修改工具**，面向 RPG Maker MV/MZ 和 Ren'Py 单机游戏。支持翻译、数据编辑、存档修改、实时作弊，以及 Android APK 迁移。

---

## 功能总览

| 模块 | RPG Maker MV/MZ | Ren'Py |
|------|:--:|:--:|
| 文本提取 | ✅ JSON / 地图事件 / 系统文本 | ✅ 脚本翻译文本 |
| AI 翻译 | ✅ 7 个渠道，并行批量 | ✅ 同左 |
| 翻译缓存与去重 | ✅ 精确 + 归一化 + 模糊匹配 | ✅ 同左 |
| 数据编辑器 | ✅ 物品/角色/职业/敌人/技能/状态 | — |
| 地图查看 | ✅ 瓦片地图 + 事件查看 + 坐标传送 | — |
| 存档修改 | ✅ 金币/物品/角色/开关/变量 | — |
| 实时控制 | ✅ 穿墙/上帝模式/自动战斗/瞬移 | — |
| 导入/导出翻译包 | ✅ | ✅ |
| 嵌入翻译到游戏 | ✅ | ✅ |
| Android 迁移 | ✅ Winlator 引擎集成 | ✅ WebView 后端 |

---

## AI 翻译渠道

| 渠道 | 说明 |
|------|------|
| OpenAI | 标准 API（支持自定义 Base URL） |
| DeepSeek | 国产高性价比大模型 |
| Doubao（豆包） | 字节跳动 |
| GLM | 智谱 AI |
| NVIDIA | NVIDIA AI |
| Xiaomi Token Plan | 小米 token 计划 / 普通 API Key |
| 百度翻译 API | 百度机器翻译 |

支持**多厂商并行翻译**：同时勾选多个渠道，工具自动轮询分配批次，最大化吞吐量。

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

### Windows（推荐）

1. 下载 `dist\RPGRenPyLocalizer\` 整个文件夹
2. 双击 `RPGRenPyLocalizer.exe`
3. **不要只发单独 exe**，`_internal` 文件夹包含 Python 运行时，缺了无法启动

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

### 2. 翻译
- 切换到「翻译工作台」
- 点击「提取文本」
- 选择翻译范围和文件
- 配置 AI 渠道和 API Key → 「保存设置」
- 点击「一键翻译全部」或「翻译选中」

### 3. 数据修改
- 切换到「数据编辑器」
- 选择分类（物品/角色/职业等）
- 选中对象 → 右侧双击值 → 修改 → 保存

### 4. 存档修改
- 切换到「存档修改」
- 点击「刷新存档列表」
- 选择存档 → 修改金币/物品/角色/开关/变量

### 5. 实时控制（仅 RPG Maker）
- 先点击「安装实时组件」并重启游戏
- 再点击「连接实时游戏」
- 然后可以使用穿墙、上帝模式、自动战斗、地图点击瞬移等

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
├── build_all.ps1              # 全量构建脚本
├── static/                    # 图标与静态资源
├── toolkit/                   # 核心工具包
│   ├── app.py                 # 主界面（tkinter，~5800 行）
│   ├── detectors.py           # 游戏引擎检测
│   ├── models.py              # 数据模型
│   ├── renpy.py               # Ren'Py 服务
│   ├── rpgmaker.py            # RPG Maker 服务
│   ├── storage.py             # JSON 持久化与翻译包
│   ├── ui_layout.py           # 响应式布局控制
│   ├── ui_theme.py            # ttk 主题
│   ├── workspace.py           # 工作空间与缓存管理
│   └── core/
│       ├── facade.py          # 无头核心（CLI/API 复用）
│       └── __main__.py
├── android_app/               # Android 壳工程
│   ├── shell/                 # Kotlin 壳（Gradle + Winlator 引擎）
│   ├── backend/               # Python 本地 API 服务
│   └── mobile_ui/             # Vue 3 移动端前端
├── AndroidAPP/                # UniApp 前端工程
├── android_offline/           # HBuilder 离线集成工程
├── ppt/                       # HTML 演示文稿
└── dist/                      # 打包输出
```

---

## Android 迁移

Android 版正在开发中，目标架构：

```
RPGRenPyLocalizer APK
├── Vue 3 / UniApp 中文界面
├── Kotlin Shell（文件权限 / WebView / 悬浮工具栏）
├── Python Core（翻译 / 数据 / 存档 / 地图）
└── 运行后端
    ├── RPG Maker → WebView
    ├── Ren'Py → 翻译补丁
    └── Windows exe → Winlator 引擎（Wine + Box64）
```

详见 [`ANDROID_APK_PLAN.md`](ANDROID_APK_PLAN.md) 和 [`WINLATOR_MIGRATION.md`](WINLATOR_MIGRATION.md)。

---

## 常见问题

### 为什么没有 Python 也能运行？
发布版用 PyInstaller 打包，`_internal` 自带 Python 运行时。

### 为什么翻译会跳过很多文本？
工具自动过滤路径、乱码、系统占位文本和非对白内容，避免误翻译。

### 地图瞬移没反应？
需要先安装实时组件 → 重启游戏 → 勾选「地图点击瞬移」→ 点击地图格子。

### `Actors.initialLevel` 改了但游戏里等级没变？
`initialLevel` 是数据库初始值，不等于当前进程实时等级。连接实时组件后可同步实时属性。

### API Key 保存在哪？安全吗？
保存在 `%APPDATA%\RPGRenPyLocalizer\settings.json`，仅当前 Windows 用户可访问。分享 exe 时不会带出去。

### 支持哪些引擎版本？
- RPG Maker MV / MZ（主要支持）
- Ren'Py（文本提取与翻译）
- RPG Maker XP / VX / VX Ace（部分支持）

---

## 说明

本工具用于单机游戏汉化、文本处理和实时修改，不面向网络游戏，不用于联机作弊。

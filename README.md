# RPGRenPyLocalizer

面向 Windows 单机游戏的 RPG Maker MV/MZ 与 Ren'Py 本地化、实时翻译和数据辅助工具。

当前重置版：**2.2.2**

- 下载版本：[GitHub Releases](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/releases)
- 查看更新：[GitHub Tags](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/tags)
- 提交建议：[lyb82ndkf@gmail.com](mailto:lyb82ndkf@gmail.com)

> 本工具面向本地单机游戏的翻译、调试与个人存档管理。修改游戏文件或存档前请保留备份，并遵守游戏许可和当地法律。

## 2.2.2 重置版更新

2.2.2 将桌面端重构为 Electron + Vue + Element Plus 界面，并继续使用本地 Python 后端处理游戏分析、翻译和实时桥接。

### 游戏库

- 添加游戏时必须选择实际的游戏 `.exe`，工具自动识别 Ren'Py 或 RPG Maker 项目。
- 游戏运行期间显示“游戏运行中”，并禁止切换或启动其他游戏，避免项目状态串线。
- 游戏被移动或删除后，启动时显示可读的中文提示，并询问是否从游戏库移除失效记录。
- 支持筛选、启动、移除和重新载入游戏。

### 翻译工作台

- 使用状态列表展示每条文本是否已翻译，减少超长原文、译文挤压表格的问题。
- 支持分页浏览、搜索和状态筛选。
- 点击条目后打开详情窗口编辑原文、译文和上下文。
- 支持提取、导入、导出、保存译文、永久写入和运行时翻译表。
- Ren'Py 游戏载入后自动隐藏仅适用于 RPG Maker 的地图和存档入口。

### Ren'Py 实时 Hook

- 安装 `zz_rpgrtl_live_bridge.rpy`，在游戏运行时捕获对话、菜单和 Text 组件文本。
- 本地桥接服务异步调用 AI，翻译结果写入缓存并通知游戏刷新。
- 增加队列、批量持久化、心跳和项目隔离，降低切换页面与持续翻译时的卡顿。
- 修复 2.2.1 及更早缓存中畸形 `{font}` 标签可能导致的崩溃。
- 安装新版 Hook 时会清理旧缓存里的孤立、全角或带空格的字体标签。
- 未配置 API 时不会把无效字体标签注入游戏；状态会显示需要配置翻译渠道。

### RPG Maker 工具

- 地图支持拖拽、横向/纵向滚动、格子悬停高亮和事件格点击。
- 事件详情可查看事件页、触发方式、出现条件和事件指令。
- 数据修改支持物品、装备、武器、开关、变量和角色。
- 存档修改支持金钱、物品、角色等级、开关、变量和完整数据查看。
- 实时修改支持玩家 HP/MP/TP、金币、移动速度、经验倍率、穿墙、无敌、自动战斗、自动存档和地图传送等能力。
- 战斗控制能力取决于具体游戏版本与桥接兼容性，连接后才会显示可用操作。

### AI 翻译

AI 配置精简为三种渠道：

| 渠道 | 默认接口 | API Key | 模型获取 |
| --- | --- | :---: | --- |
| OpenAI | `https://api.openai.com/v1` | 需要 | 从兼容接口读取模型 |
| Anthropic | `https://api.anthropic.com` | 需要 | 从兼容接口读取模型 |
| Ollama | `http://127.0.0.1:11434` | 不需要 | 自动检测本机已安装模型 |

- OpenAI 和 Anthropic 支持自定义兼容接口，只需填写 URL、API Key，再点击获取模型。
- Ollama 切换后自动访问本机 `/api/tags`，模型会进入下拉列表。
- 提供独立的“测试翻译”区域，不要求先选择游戏或工作台条目。
- “读取设置”与“保存设置”均提供明确结果提示。
- 兼容旧 Python 版本的本机设置缓存，并自动迁移旧渠道名称。

### 设置与更新

- 设置页显示的版本来自应用构建信息，不在页面中写死。
- 可检查 GitHub 最新标签，有新版本时跳转 Releases 下载。
- 左侧导航可显示新版本状态。
- 提供项目主页和邮件反馈入口。

## 支持范围

| 功能 | RPG Maker MV/MZ | Ren'Py |
| --- | :---: | :---: |
| 游戏识别与启动 | 支持 | 支持 |
| 文本提取与翻译工作台 | 支持 | 支持 |
| AI 批量翻译 | 支持 | 支持 |
| 运行时文本捕获与替换 | JS 实时组件 | Ren'Py Hook |
| 数据库修改 | 支持 | 不适用 |
| 地图与事件查看 | 支持 | 不适用 |
| 存档修改 | 支持 | 不适用 |
| 实时属性修改 | 支持 | 有限支持 |

RPG Maker XP、VX 和 VX Ace 只能识别部分资源，不保证实时组件、地图和存档功能可用。

## 安装

### 使用 Windows 安装包

1. 打开 [Releases](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/releases)。
2. 下载最新的 `RPGRenPyLocalizer Setup x.x.x.exe`。
3. 运行安装程序并选择安装目录。
4. 从桌面或开始菜单启动 RPGRenPyLocalizer。

发布版已经包含 Python 后端，目标电脑不需要单独安装 Python 或 Node.js。

### 添加游戏

1. 进入“游戏库”。
2. 点击添加游戏并选择游戏启动 `.exe`，不要只选择文件夹。
3. 等待工具识别引擎后选择该游戏。
4. 点击启动，或进入对应功能页面。

游戏运行时不能切换到其他项目。请先正常退出当前游戏，等待状态变为未运行。

## Ren'Py 实时翻译

### 首次使用

1. 在游戏库中添加并选择 Ren'Py 游戏的 `.exe`。
2. 进入“AI 设置”，选择 OpenAI、Anthropic 或 Ollama。
3. 填写接口信息、获取并选择模型，然后执行“测试翻译”。
4. 进入“实时翻译”，点击启动实时翻译。
5. 工具会安装 Hook、启动本地桥接服务并启动游戏。
6. 游戏中出现的新文本会被捕获，翻译完成后自动写入运行时翻译表。

### 从旧版本升级

2.2.2 修改了字体标签清理和缓存格式。升级后请执行一次：

1. 选择原来的 Ren'Py 游戏。
2. 进入“实时翻译”并点击启动，工具会自动重新安装 Ren'Py Hook。
3. 完全退出并重新启动游戏。

安装过程会更新 `game/zz_rpgrtl_live_bridge.rpy`，并清理旧缓存中可能导致 `'/font' closes a text tag that isn't open` 的数据。

### 工作原理

```text
Ren'Py 渲染文本
       |
       v
zz_rpgrtl_live_bridge.rpy 捕获并清理文本
       |
       v
本地 HTTP 桥接 <-> RPGRenPyLocalizer Python 后端
       |
       v
OpenAI / Anthropic / Ollama 异步翻译
       |
       v
原子写入项目缓存并通知游戏刷新
       |
       v
游戏下一次渲染时显示译文
```

Hook 会保留 Ren'Py 控制标记的顺序，并过滤可能破坏渲染的字体标签。由于不同游戏可能重写 Character、Text 或 screen，少数深度定制项目仍可能需要单独适配。

## Ollama 本地翻译

1. 安装并启动 Ollama。
2. 在终端下载模型，例如：

```powershell
ollama pull qwen2.5:7b
```

3. 在工具中选择“Ollama 本地模型”。
4. 保持默认地址 `http://127.0.0.1:11434`，点击“检测本地模型”。
5. 从下拉列表选择模型并测试翻译。

检测失败时，先运行：

```powershell
ollama list
```

如果命令不可用或服务未启动，工具无法读取本地模型。Ollama 模式不需要也不会保存 API Key。

## RPG Maker 使用说明

### 地图与事件

- 进入地图页后选择地图，使用鼠标拖拽画布或滚动条移动。
- 悬停格子时格子高亮；点击事件格可查看该位置的事件列表。
- 事件详情显示事件页条件、触发方式和指令。
- 连接实时组件后，地图可标记当前玩家位置并执行传送。

### 数据与存档

- “数据修改”用于编辑项目数据库和连接后的实时数据。
- “存档”页先选择存档槽，再修改金钱、物品、角色、开关或变量。
- 写回前建议保留原存档；不同插件生成的自定义存档字段可能无法自动解析。

### 实时组件

1. 选择 RPG Maker MV/MZ 游戏。
2. 进入“实时修改”并安装实时组件。
3. 完全退出并重新启动游戏，让插件被引擎加载。
4. 进入地图后连接运行中的游戏。

“安装实时组件”只写入游戏项目所需文件，不会打开 VS Code。

## 配置与缓存

| 内容 | 位置 |
| --- | --- |
| AI 渠道、URL、模型和密钥 | `%APPDATA%\RPGRenPyLocalizer\settings.json` |
| 全局翻译记忆 | `%APPDATA%\RPGRenPyLocalizer\translation_memory.json` |
| 项目工作区与实时翻译缓存 | `<游戏目录>\.rpgrtl_workspace\` |
| 自动备份 | `<游戏目录>\.rpgrtl_backup\` |
| Ren'Py 实时 Hook | `<游戏目录>\game\zz_rpgrtl_live_bridge.rpy` |

API Key 只保存在当前 Windows 用户的本机配置中，不应提交到 Git、截图或问题报告。公开日志前请检查其中是否包含接口地址、文件路径和敏感信息。

## 常见问题

### 启动游戏时提示找不到文件

游戏可能被移动、重命名或删除。确认窗口中可以选择“从游戏库删除”或“保留记录”；如果只是移动了游戏，请删除旧记录后重新选择新的 `.exe`。

### Ren'Py 报错 `/font` closes a text tag that isn't open

安装 2.2.2 后重新安装 Hook并重启游戏。新版会同时清理服务器缓存、项目缓存和运行时文本中的畸形字体标签。

### 开启实时翻译后没有译文

依次确认：

1. AI 设置中的测试翻译成功。
2. 已选择模型，OpenAI/Anthropic 已填写 API Key。
3. Ollama 服务正在运行并能执行 `ollama list`。
4. 实时翻译状态有心跳且捕获数量持续增加。
5. 游戏已在安装新版 Hook 后完整重启。

### 测试翻译没有反应

2.2.2 已将测试功能与游戏选择解耦。输入测试原文、选择模型并点击“开始测试”，结果或具体错误会显示在测试区域。

### 地图、存档或实时修改不可用

这些页面主要用于 RPG Maker MV/MZ。Ren'Py 项目会隐藏不适用入口。实时数据还要求安装组件、重启游戏并进入地图。

### 修改前如何恢复

优先使用 `.rpgrtl_backup` 中的备份。对重要游戏和存档，建议额外复制整个游戏目录或存档目录。

## 从源码运行

要求：Windows、Python 3.11+、Node.js 20+、npm。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pyinstaller
npm install
npm run build:renderer
npm start
```

开发模式下 Electron 会启动本地 Python API 后端；前端通过 preload 暴露的安全接口访问后端和系统功能。

## 测试与构建

运行后端回归测试：

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

检查 Python 文件：

```powershell
python -m py_compile toolkit/api/server.py toolkit/renpy.py
```

构建 Windows 安装包：

```powershell
.\build_electron_release.ps1 -SkipNpmInstall
```

输出目录：

```text
release-electron/
├── RPGRenPyLocalizer Setup x.x.x.exe
└── win-unpacked/
```

## 项目结构

```text
RPGRenPyLocalizer/
├── electron/                    # Electron 主进程、preload 与 Vue 前端
│   └── renderer/src/            # 翻译工作台和各功能页面
├── toolkit/
│   ├── api/server.py            # Electron 本地 HTTP API
│   ├── renpy.py                 # Ren'Py 分析、Hook 与实时翻译
│   ├── rpgmaker.py              # RPG Maker 数据、存档、地图与桥接
│   ├── storage.py               # 配置、缓存与翻译包
│   └── workspace.py             # 游戏库和项目工作区
├── tests/                       # 后端回归测试
├── api_server_entry.py          # 打包后端入口
├── build_electron_release.ps1   # 一体化构建脚本
├── package.json                 # 应用版本和 Electron Builder 配置
└── README.md
```

## 反馈与贡献

- 问题与建议：[GitHub Issues](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/issues)
- 版本与下载：[GitHub Releases](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/releases)
- 邮件：[lyb82ndkf@gmail.com](mailto:lyb82ndkf@gmail.com)

提交问题时请附上工具版本、游戏引擎、复现步骤和已脱敏的错误信息。请勿上传游戏本体、付费资源、API Key 或包含个人信息的存档。

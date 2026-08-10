# RPGRenPyLocalizer

面向 Windows 单机游戏的 RPG Maker MV/MZ 与 Ren'Py 本地化、实时翻译和数据辅助工具，支持 PC 桌面端与 Android 移动端双端运行。

当前版本：**3.1.0（PC / Android）**

- 下载版本：[GitHub Releases](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/releases)
- 查看更新：[GitHub Tags](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/tags)
- 提交建议：[lyb82ndkf@gmail.com](mailto:lyb82ndkf@gmail.com)

> 本工具面向本地单机游戏的翻译、调试与个人存档管理。修改游戏文件或存档前请保留备份，并遵守游戏许可和当地法律。

## 3.1.0 版本更新

3.0.0 将 PC 端已经验证的 Ren'Py 实时翻译调度策略同步到 Android，并把两端发布版本统一为 **3.0.0**。本次重点不是改变用户的 AI 配置，而是让单批数量、并发数和请求间隔真正按已保存的设置工作。

### PC 端更新

- **300 条预读窗口**：Ren'Py 会从当前对话附近提取并补齐后续文本，最多维持 300 条未翻译预读，减少玩家读到新一句才开始请求 AI 的情况。
- **按配置并行批译**：严格使用 AI 设置中的“单批数量 × 并发线程”派发批次；例如设置 50 条、4 并发时，最多同时处理 4 个 50 条批次，而不是退化为逐条请求。
- **当前对话优先**：当前屏幕文本不会被普通失败退避阻塞。大批响应不完整时，会优先对当前句做即时补救；其余遗漏文本继续以小批并行修复。
- **更可靠的脚本锚点**：运行时文本与脚本中带 Ren'Py 标签的同一句也能匹配，从而正确补充同文件、同语言的后续预读队列。
- **选项注入安全修复**：不再修改 Ren'Py 菜单 AST 原始选项，只在显示层替换并套用中文字体，避免重复进入菜单后选项错位、污染或显示方框。
- **实时状态更可读**：实时翻译状态会说明预读数量、并行批次、补救批次及当前句即时补救，便于判断是 API、队列还是缓存命中导致等待。

### Android App 更新

- **同步 PC 实时调度**：Ren'Py Hook 预读窗口提升到 300 条；手机端会先把当前对话放在队首，再用已保存的批大小填充同一批次并并行请求 AI。
- **配置不再被暗中截断**：手机端单批最高支持 200 条、实际并发最高支持 8 路；运行中会读取 AI 设置中的批大小、并发数和请求间隔，而不是固定使用旧的 4 条快速批或 4 路线程上限。
- **当前句即时回退**：当前对话忽略普通失败冷却；大批返回缺句时先单独重试当前句，再把其余遗漏文本按小批立即补救，避免等待 5 秒后才重新入队。
- **实时嵌入与选项安全性**：翻译结果写入运行时缓存并通知游戏刷新；菜单不再改写原始选项数据，显示层负责中文字体包装与替换。
- **统一版本发布**：Android `versionName` 为 `3.0.0`，`versionCode` 为 `300000`，可用于覆盖此前同签名的旧调试包。

### 未知游戏 Agent（PC）

- 游戏库现在可以导入带有明确文件信号的 Unity、Unreal Engine 4/5、Godot 和 Electron/Web 游戏；单独选择未知 `.exe` 也会标记为 Generic Windows Game。
- Agent 工作台提供只读引擎扫描、资源信号、候选文本提取、AI 分析计划和工具清单。
- 可将已保存译文生成到 `.rpgrtl_workspace/unknown_runtime_game` 隔离副本，再启动副本验证；原游戏目录不会写入，副本可直接删除回滚。
- Unity、Unreal、Godot 的专用资源解析器和进程 Hook 通过工具清单预留适配点，后续按具体游戏启用，不对未知进程盲目注入。

## 2.3.0 / 4.0 历史版本更新

2.3.0 是在 2.2.2 Electron 重置版基础上的一次**翻译链路、AI 配置、RPG Maker 安全写回与 Android App 可用性**集中修复版本。PC 端版本号为 **2.3.0**，Android 端版本号为 **4.0**。

### 2.3.0 重点概览

- **翻译范围更安全**：RPG Maker 只展示并翻译 `database` 与 `dialogue`，不再把 `event`、`script`、`system` 等高风险文本暴露给普通批译流程；Ren'Py 只展示并翻译对话与选项。
- **批译链路重做**：PC 端批译改为按条目 ID 发送 JSON，AI 返回 JSON 后再按 `entry_id` 写回，避免“50/200 条里顺序错位、译文写回到错误文本、AI 返回原文”等问题。
- **并发与限流可控**：AI 设置新增批量大小、并发线程、请求间隔、429 重试次数和请求超时秒，适配 OpenAI 兼容接口、Anthropic、Ollama 以及 NVIDIA 等限流较严格的免费接口。
- **AI 设置更清晰**：输入框增加明确标签，不再只依赖 placeholder；新增“保存配置并命名 / 打开已保存配置 / 删除配置”，方便在不同 API 服务商与模型之间切换。
- **RPG Maker 流程调整**：RPG Maker 不再在左侧暴露“实时翻译”入口。正确流程是先导入/提取文本，在“翻译”页完成 database/dialogue 翻译，再启动游戏使用运行时翻译表。
- **新手教程重写**：教程改为与当前工具逻辑一致，按“导入游戏 → 载入游戏 → 判断引擎 → Ren'Py 流程 / RPG Maker 流程 → AI 设置 → 数据功能”的顺序引导。
- **Android App 重构**：移动端改为 Vite + Vue 3 WebUI，补齐游戏库、翻译、数据、AI 设置等移动工作台能力，并修复导入、SVG、缩放、第三方加载页暴露等问题。

### PC 端：游戏库

- 添加游戏时仍建议选择实际的游戏启动 `.exe`，工具自动识别 Ren'Py 或 RPG Maker 项目。
- 游戏运行期间显示“游戏运行中”，并禁止切换或启动其他游戏，避免项目状态串线。
- 游戏被移动或删除后，启动时显示可读的中文提示，并询问是否从游戏库移除失效记录。
- 支持筛选、启动、移除和重新载入游戏。
- RPG Maker MV/MZ 会自动准备 Web/JS 运行所需桥接文件；Ren'Py 会按需准备 Hook 文件。

### PC 端：翻译工作台

- RPG Maker 只显示可安全替换的 `database` 与 `dialogue`：
  - `database`：物品、武器、防具、技能、角色、敌人、状态等数据库文本。
  - `dialogue`：对话、选项、滚动文本等面向玩家的文本。
  - 默认不向用户展示/批译 `event`、`script`、`system` 等容易引起游戏崩溃的文本类型。
- Ren'Py 只显示并翻译对话与选项，不处理脚本控制逻辑。
- 使用状态列表展示每条文本是否已翻译，减少超长原文、译文挤压表格的问题。
- 支持分页浏览、搜索、状态筛选、详情编辑、保存译文、导入/导出翻译包、永久写入和运行时翻译表生成。
- AI 批译时会显示批量进度、成功/失败数量与当前状态，避免点击后看不出是否正在工作。
- RPG Maker 游戏载入后会隐藏不适用的“实时翻译”入口；Ren'Py 游戏载入后会隐藏仅适用于 RPG Maker 的地图和存档入口。

### PC 端：AI 批译与写回

AI 批译协议从“纯文本数组”升级为“带条目 ID 的 JSON 条目”，核心目标是**稳定写回**：

```json
{
  "entries": [
    { "entry_id": "dialogue:Map001:12", "source": "Hello." },
    { "entry_id": "database:Items:1:name", "source": "Potion" }
  ]
}
```

AI 应返回：

```json
{
  "translations": [
    { "entry_id": "dialogue:Map001:12", "target": "你好。" },
    { "entry_id": "database:Items:1:name", "target": "药水" }
  ]
}
```

- 前端按 `entry_id` 解析并写回，不再依赖返回顺序。
- 提示词强调：目标语言为简体中文时必须输出简体中文，不允许原样返回英文/日文原文。
- 单批过大导致超时时，会自动拆分子批重试，降低“一批 200 条全部失败”的概率。
- 对 HTTP 429 Too Many Requests 会按设置进行退避重试；用户可自行降低并发、减小单批数量或增加请求间隔。
- 请求超时会显示明确的 504/timeout 提示，并建议减小批量或增加超时秒数。

### PC 端：AI 设置

AI 配置保留三种主渠道，并支持兼容接口：

| 渠道 | 默认接口 | API Key | 模型获取 |
| --- | --- | :---: | --- |
| OpenAI | `https://api.openai.com/v1` | 需要 | 从兼容接口读取模型 |
| Anthropic | `https://api.anthropic.com` | 需要 | 从兼容接口读取模型 |
| Ollama | `http://127.0.0.1:11434` | 不需要 | 自动检测本机已安装模型 |

- OpenAI 和 Anthropic 支持自定义兼容接口，只需填写 Base URL、API Key，再点击获取模型。
- Ollama 切换后自动访问本机 `/api/tags`，模型会进入下拉列表。
- 设置页为接口类型、接口地址、API Key、模型、批量大小、并发线程、请求间隔、429 重试、请求超时和目标语言提供明确标签。
- 新增“保存为配置”：可以给当前 API 组合命名，例如“OpenAI 主号”“NVIDIA 免费”“本地 Ollama”。
- 新增“打开配置”：可从已保存配置中快速切换服务商、模型、批量参数和目标语言。
- 新增“删除配置”：清理不用的配置，避免设置面板堆积。
- 提供独立“测试翻译”区域，不要求先选择游戏或工作台条目。
- 兼容旧 Python 版本的本机设置缓存，并自动迁移旧渠道名称。

### PC 端：Ren'Py 实时 Hook

- 安装 `zz_rpgrtl_live_bridge.rpy`，在游戏运行时捕获对话、菜单和 Text 组件文本。
- 本地桥接服务异步调用 AI，翻译结果写入缓存并通知游戏刷新。
- 增加队列、批量持久化、心跳和项目隔离，降低切换页面与持续翻译时的卡顿。
- 修复 2.2.1 及更早缓存中畸形 `{font}` 标签可能导致的崩溃。
- 安装新版 Hook 时会清理旧缓存里的孤立、全角或带空格的字体标签。
- 未配置 API 时不会把无效字体标签注入游戏；状态会显示需要配置翻译渠道。

### PC 端：RPG Maker 工具

- 地图支持拖拽、横向/纵向滚动、格子悬停高亮和事件格点击。
- 事件详情可查看事件页、触发方式、出现条件和事件指令，但事件脚本不进入普通批译写回流程。
- 数据修改支持物品、装备、武器、开关、变量和角色。
- 存档修改支持金钱、物品、角色等级和完整数据查看；开关、变量统一放在“数据修改”页实时操作。
- RPG Maker MV/MZ 会优先使用 WebView/JS 运行方式，不要求用户选择 Winlator。
- RPG Maker 运行时翻译采用“先翻译、后启动/载入”的方式，把已翻译的 database/dialogue 映射注入运行时环境，避免边 Hook 边替换造成崩溃。
- 实时修改支持玩家 HP/MP/TP、金币、移动速度、经验倍率、穿墙、无敌、自动战斗、自动存档和地图传送等能力。
- 战斗控制能力取决于具体游戏版本与桥接兼容性，连接后才会显示可用操作。

### Android App 端：4.0 重构与优化

- 移动端前端由旧方案改为 **Vite + Vue 3**，功能结构向 PC 端靠齐。
- App 起始工作台采用竖屏布局，集中展示游戏库、翻译、数据和 AI 设置；只有进入游戏运行态后才切换为横屏。
- 横屏游戏态隐藏底部导航和普通工作台入口，只保留游戏内工具、实时修改、数据库统计和快速操作，减少遮挡。
- 顶部/底部导航尺寸、WebView `textZoom`、字体和间距均缩小，缓解手机端 UI 偏大、拥挤和遮挡问题。
- 将大量 emoji 图标替换为 SVG 矢量图标，并修复 Android `file:///android_asset/` 环境下 SVG 路径不可见的问题。
- 游戏导入/扫描/启动增加遮罩动画和进度提示，避免用户直接看到第三方加载页。
- 替换 MTool/Discord/Click To Exit 等第三方提示文案，统一显示 RPGRenPyLocalizer 自己的加载与错误提示。
- 修复 Android 导入 RPG Maker 项目时的 UI 线程异常：`Only the original thread that created a view hierarchy can touch its views`。
- RPG Maker MV/MZ 在 App 端优先走内置 WebView 运行；Winlator/兼容运行器只用于 Windows exe 或需要外部兼容层的 Ren'Py/EXE 项目。
- 修复部分 RPG Maker 音频资源加载失败时播放刺耳默认报错音的问题，尽量静默降级而不是打断游玩。
- App 端 AI 设置补齐 OpenAI、Anthropic、Ollama 三种渠道，不再只有单个 API Key 输入框。
- App 端翻译页支持调用已保存 AI 设置进行批译和保存译文。
- 横屏游戏工具页展示金钱、地图 ID、坐标、队伍人数、数据库记录数量、已修改数量，以及角色/物品/武器/装备/技能/敌人等数据库统计。
- 右上角工具按钮由黄色块改为深色半透明胶囊按钮，降低对游戏画面的遮挡。

### 从 2.2.2 到 2.3.0 / Android 4.0 的变化一览

| 模块 | 2.2.2 | 2.3.0 / 4.0 |
| --- | --- | --- |
| PC 架构 | Electron + Vue + Element Plus 重置版 | 保持桌面架构，重点修复翻译链路、批译写回、AI 设置和 RPG Maker 安全流程 |
| 翻译范围 | 工作台可见范围较宽，RPG Maker event/system 存在误翻风险 | RPG Maker 仅 database/dialogue；Ren'Py 仅对话/选项，降低写坏游戏风险 |
| AI 批译写回 | 更依赖文本顺序和普通数组返回 | 使用 `{ entries }` / `{ translations }` JSON 协议，通过 `entry_id` 精准写回 |
| 批译稳定性 | 大批量请求超时可能导致整批失败 | 支持请求超时秒、429 重试、并发线程、请求间隔、自动拆批 |
| AI 设置 | 可选 OpenAI / Anthropic / Ollama，布局主要依赖 placeholder | 输入框带清晰标签，支持命名保存、打开、删除多套配置 |
| RPG Maker 实时翻译 | 偏向实时 Hook/实时替换思路 | 改为先翻译 database/dialogue，再载入游戏使用运行时翻译表 |
| Ren'Py | Hook 修复字体标签崩溃，实时捕获对话/菜单 | 保留 2.2.2 Hook 修复，并限制普通工作台只翻译对话/选项 |
| 教程 | 仍包含旧逻辑 | 按当前双引擎流程重写，区分 Ren'Py 与 RPG Maker 使用方式 |
| Android UI | 功能不足，界面偏大，emoji 多 | Vite + Vue 3 重构，SVG 图标，竖屏工作台 + 横屏游戏态，布局更紧凑 |
| Android 游戏启动 | RPG Maker/EXE 流程容易混淆，可能暴露第三方加载页 | RPG Maker 优先 WebView；Winlator 仅用于 Windows exe/部分 Ren'Py；加载页与错误文案统一 |
| Android 导入稳定性 | 导入 RPG Maker 时可能触发 UI 线程崩溃 | 扫描结果回到主线程更新 UI，修复 Android View 线程异常 |
| Android 游戏辅助 | 工作台与游戏态边界不清 | 横屏只显示游戏内数据、实时修改与数据库统计，减少导航遮挡 |

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
| 运行时文本捕获与替换 | 预翻译运行时映射 / JS 组件 | Ren'Py Hook |
| 数据库修改 | 支持 | 不适用 |
| 地图与事件查看 | 支持 | 不适用 |
| 存档修改 | 支持 | 不适用 |
| 实时属性修改 | 支持 | 有限支持 |

RPG Maker XP、VX 和 VX Ace 只能识别部分资源，不保证实时组件、地图和存档功能可用。

## 安装

### PC端 (Windows)

1. 打开 [Releases](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/releases)。
2. 下载最新的 `RPGRenPyLocalizer Setup 3.0.0.exe`（安装版）或 `RPGRenPyLocalizer 3.0.0.exe`（免安装便携版）。
3. 安装版按提示安装；便携版解压即用。
4. 从桌面或开始菜单启动 RPGRenPyLocalizer。

发布版已经包含 Python 后端，目标电脑不需要单独安装 Python 或 Node.js。

### Android 端

1. 下载最新发布的 `RPGRenPyLocalizer-3.0.0.apk`。
2. 在手机端安装。App 内嵌新版移动 WebUI；RPG Maker MV/MZ 优先使用内置 WebView，Windows exe 或需要兼容层的 Ren'Py 项目再使用 Winlator/兼容运行器。

### 添加游戏

#### PC 端

1. 进入“游戏库”。
2. 点击添加游戏并选择游戏启动 `.exe`，不要只选择文件夹。
3. 等待工具识别引擎后选择该游戏。
4. 点击启动，或进入对应功能页面。

游戏运行时不能切换到其他项目。请先正常退出当前游戏，等待状态变为未运行。

#### Android 端

1. 进入竖屏“游戏库”。
2. RPG Maker MV/MZ 选择游戏目录或包含 `www/index.html`、`Game.rpgproject`、`package.json` 的目录，使用“RPGMaker WebView”启动。
3. Ren'Py Web 项目优先尝试 WebView；Windows exe 或必须依赖 Windows 环境的项目再选择兼容运行器。
4. 导入、扫描、启动时请等待进度遮罩结束；进入游戏后 App 会切换为横屏游戏态。

## Ren'Py 实时翻译

### 首次使用

1. 在游戏库中添加并选择 Ren'Py 游戏的 `.exe`。
2. 进入“AI 设置”，选择 OpenAI、Anthropic 或 Ollama。
3. 填写接口信息、获取并选择模型，然后执行“测试翻译”。
4. 先启动 Ren'Py 游戏并进入游戏内容。
5. 回到工具进入“实时翻译”，点击启动实时翻译。
6. 工具会自动准备 Hook、启动本地桥接服务；游戏中出现的新文本会被捕获，翻译完成后自动写入运行时翻译表。

### 从旧版本升级

2.2.2 修改了字体标签清理和缓存格式。升级后请执行一次：

1. 选择原来的 Ren'Py 游戏。
2. 进入“实时翻译”并点击启动，工具会自动更新 Ren'Py Hook。
3. 完全退出并重新启动游戏，再按“先启动游戏、后启动实时翻译”的顺序操作。

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
- “存档”页先选择存档槽，再修改金钱、物品和角色等级；开关与变量请在游戏运行后进入“数据修改”页操作。
- 写回前建议保留原存档；不同插件生成的自定义存档字段可能无法自动解析。

### 翻译优先流程与实时组件

1. 选择 RPG Maker MV/MZ 游戏。
2. 进入“翻译”页，先提取 `database` 与 `dialogue` 文本。
3. 在 AI 设置中测试成功后，回到“翻译”页执行 AI 批译；建议限流接口先使用较小单批和较低并发。
4. 检查译文后保存，并生成运行时翻译表。
5. 再从游戏库启动/载入游戏。工具会把已翻译文本用于运行时替换。

发布版目录说明：普通项目的桥接文件位于 `<游戏目录>\js\plugins\RPGRenPyBridge.js`；如果游戏使用 `www` 子目录，则位于 `<游戏目录>\www\js\plugins\RPGRenPyBridge.js`。修改桥接后必须完全退出并重新启动游戏，不能只返回标题画面。

2.3.0 起 RPG Maker 不再使用“边玩边实时 Hook 批译”的普通入口，因为 event/script/system 等文本被误替换后很容易造成游戏崩溃。工具会优先把已提取的 database/dialogue 写入安全的运行时映射；游戏运行中新出现的文本可后续重新提取、补译并再载入。

## 配置与缓存

| 内容 | 位置 |
| --- | --- |
| AI 渠道、URL、模型、密钥、批译参数和命名配置 | `%APPDATA%\RPGRenPyLocalizer\settings.json` |
| 全局翻译记忆 | `%APPDATA%\RPGRenPyLocalizer\translation_memory.json` |
| 项目工作区与实时翻译缓存 | `<游戏目录>\.rpgrtl_workspace\` |
| 自动备份 | `<游戏目录>\.rpgrtl_backup\` |
| Ren'Py 实时 Hook | `<游戏目录>\game\zz_rpgrtl_live_bridge.rpy` |

API Key 只保存在当前 Windows 用户的本机配置中，不应提交到 Git、截图或问题报告。公开日志前请检查其中是否包含接口地址、文件路径和敏感信息。

## 常见问题

### 启动游戏时提示找不到文件

游戏可能被移动、重命名或删除。确认窗口中可以选择“从游戏库删除”或“保留记录”；如果只是移动了游戏，请删除旧记录后重新选择新的 `.exe`。

### Ren'Py 报错 `/font` closes a text tag that isn't open

升级到 2.2.2 后重新载入项目并重启游戏。工具会自动更新 Hook，同时清理服务器缓存、项目缓存和运行时文本中的畸形字体标签。

### RPG Maker 启动后没有显示译文

依次确认：

1. AI 设置中的测试翻译成功。
2. 已选择模型，OpenAI/Anthropic 已填写 API Key；Ollama 服务正在运行并能执行 `ollama list`。
3. 已在“翻译”页提取并翻译 `database` / `dialogue`，且译文状态显示为已完成。
4. 已点击保存译文或生成运行时翻译表。
5. RPG Maker 游戏已在工具自动准备桥接后完整重启。
6. 如果是新出现的对白，请重新提取、补译后再载入游戏。

### 测试翻译没有反应

2.3.0 已将测试功能与游戏选择解耦，并为输入框增加明确标签。输入测试原文、选择模型并点击“开始测试”，结果或具体错误会显示在测试区域。

### 地图、存档或实时修改不可用

这些页面主要用于 RPG Maker MV/MZ。Ren'Py 项目会隐藏不适用入口。实时数据需要重启已自动准备桥接的游戏并进入地图；Android 横屏游戏态会把相关数据集中到游戏工具页。

### 修改前如何恢复

优先使用 `.rpgrtl_backup` 中的备份。对重要游戏和存档，建议额外复制整个游戏目录或存档目录。

## 从源码运行与构建

要求：Windows、Python 3.11+、Node.js 20+、npm、Java 17+ (仅Android)、Gradle 9.5+ (仅Android)。

### PC 桌面端开发与构建
```powershell
# 初始化
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pyinstaller
npm install

# 运行开发环境
npm run build:renderer
npm start

# 构建 Windows 安装包 (同时产出 Setup 与 Portable)
npm run dist
```

输出目录：`release-electron/`

### Android 端开发与构建
```powershell
# 依赖安装
cd android_app\mobile_ui_src
npm install

# 使用一键脚本构建 Android APK
cd ..\..
powershell -ExecutionPolicy Bypass -File .\build_all.ps1 -Debug
```

输出目录：`dist\android\latest\`

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
├── android_app/                 # Android Shell、移动端 WebUI 与 APK 构建脚本
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

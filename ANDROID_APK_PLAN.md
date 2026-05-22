# RPGRenPyLocalizer Android / APK 迁移计划

这份计划用于把当前 Windows 桌面版 `RPGRenPyLocalizer` 逐步迁移到 Android 手机上使用。目标不是简单“把 exe 转 apk”，而是把现有工具拆成可复用核心、移动端界面、游戏运行层、触控映射层四部分。

## 1. 先说结论

当前项目可以迁移到 Android，但不能 1:1 直接打包。

原因如下：

- 当前界面使用 `tkinter`，Android 不支持。
- 当前打包方式是 PyInstaller 生成 Windows exe，Android 不支持运行这个 exe。
- Android 不能原生运行 Windows 游戏 exe，如果用户要在手机里运行 `.exe` 游戏，需要 Winlator、Wine、Box64/Box86 这类兼容层。
- RPG Maker MV/MZ 本质是 HTML5 游戏，Android 上有机会用 WebView 直接加载游戏资源。
- Ren'Py 官方支持 Android 导出，但 Windows 版 Ren'Py exe 不能直接在 Android 原生运行。
- 翻译、文本提取、AI 翻译、缓存、数据解析这类 Python 逻辑可以复用。

推荐路线：

```text
现有 Windows 版
  |
  | 阶段 1：拆出无 UI 核心逻辑
  v
EngineCore
  |
  | 阶段 2：提供本地 HTTP API
  v
Local API Server
  |
  | 阶段 3：移动端 Web UI / Android 壳
  v
Android APK
  |
  | 阶段 4：接入游戏运行方式
  v
RPG Maker WebView / Ren'Py Android / Winlator exe
```

## 2. Android 版目标功能

第一版 Android 工具建议实现这些能力：

- 选择手机存储中的游戏目录。
- 自动识别 RPG Maker MV/MZ、Ren'Py、普通 exe 目录。
- 对 RPG Maker MV/MZ 读取 `www/data` 或 `data` 目录。
- 对 Ren'Py 读取 `game` 目录、`.rpy`、`.rpyc`、`.rpa`。
- 支持翻译工作台、AI 翻译、缓存、去重、导入导出翻译文件。
- 支持 RPG Maker MV/MZ 的数据查看、物品、角色、开关、变量、地图查看。
- 支持移动端作弊面板，包含金币、物品、角色状态、开关变量等。
- 支持自定义虚拟按钮位置、大小、透明度。
- 支持自定义虚拟摇杆位置、大小、灵敏度。
- 支持保存多套按键布局。
- 支持将工具面板悬浮在游戏上方。

需要分情况实现的能力：

- RPG Maker MV/MZ：优先尝试 WebView 原生运行。
- Ren'Py：优先做翻译与补丁工具，运行游戏建议走 Ren'Py 官方 Android 包或外部运行器。
- Windows exe：不能原生运行，需要调用 Winlator 等兼容层。

## 3. 总体架构

推荐把项目拆成 5 层。

```text
RPGRenPyLocalizer/
  toolkit/
    core/
      project_core.py
      translation_core.py
      ai_core.py
      rpgmaker_core.py
      renpy_core.py
      runtime_core.py
      save_core.py
    api/
      server.py
      routes_project.py
      routes_translate.py
      routes_runtime.py
      routes_data.py
    app.py                  # Windows tkinter UI，只负责桌面界面

android_app/
  backend/
    main.py                 # Android 内本地服务入口
  mobile_ui/
    src/                    # Vue / Web 前端
  shell/
    Android project         # WebView、文件权限、悬浮窗、输入映射
```

### 3.1 EngineCore

`EngineCore` 是第一阶段最关键的重构目标。

它不能导入 `tkinter`，不能依赖 `StringVar`、`TreeView`、窗口事件，只负责业务逻辑。

需要迁移进去的能力：

- 项目识别：来自 `toolkit/detectors.py`。
- 工作区与配置：来自 `toolkit/workspace.py`。
- RPG Maker 解析与实时桥：来自 `toolkit/rpgmaker.py`。
- Ren'Py 解析与补丁：来自 `toolkit/renpy.py`。
- 翻译条目、缓存、去重、AI 翻译调度。
- 嵌入翻译、加载翻译、备份、恢复。
- 地图、事件、开关、变量、物品、角色数据。

### 3.2 Local API Server

Android UI 不直接调用 Python 类，而是调用本地 HTTP API。

示例接口：

```text
POST /api/project/load
GET  /api/project/current
GET  /api/translate/entries
POST /api/translate/start
GET  /api/translate/job/{id}
POST /api/translate/apply
POST /api/translate/embed
GET  /api/data/categories
GET  /api/data/items
POST /api/data/item/update
GET  /api/runtime/state
POST /api/runtime/command
GET  /api/maps
GET  /api/maps/{id}
POST /api/runtime/teleport
GET  /api/layouts
POST /api/layouts/save
```

### 3.3 Android Mobile UI

建议用 Web UI 做移动端界面，再放进 Android WebView。

推荐技术：

- Vue 3
- Vite
- Vant 或 Naive UI Mobile
- Canvas / SVG 绘制地图
- IndexedDB 或本地 API 保存按键布局

移动端页面建议：

- 首页：选择游戏目录、识别引擎、启动方式。
- 翻译：文本列表、筛选、AI 翻译、进度、导出、嵌入。
- 数据：物品、角色、开关、变量、存档备份。
- 地图：缩放拖拽、事件格子、传送、当前位置。
- 悬浮控制：金币、HP、MP、TP、倍率、穿墙、加速、战斗按钮。
- 按键布局：拖拽按钮、摇杆、保存布局。

### 3.4 Android Shell

Android 壳负责系统能力：

- 申请文件夹访问权限。
- 通过 Storage Access Framework 读取游戏目录。
- 打开 WebView 显示移动端 UI。
- 启动本地 Python 服务。
- 申请悬浮窗权限。
- 保存虚拟按键布局。
- 调用外部 Winlator 或其它运行器。

可选方案：

- `ChaquoPy + Kotlin`：更像正规 Android 项目，适合长期维护。
- `python-for-android / Buildozer`：更容易复用 Python，但 Android 原生能力接入麻烦。
- `Capacitor + 原生插件 + 后端服务`：UI 开发快，但 Python 集成要额外处理。

我建议优先使用：

```text
Kotlin Android 壳 + WebView UI + Python Core 服务
```

如果先做原型，可以用：

```text
Buildozer / python-for-android + WebView
```

## 4. 游戏运行方案

### 4.1 RPG Maker MV/MZ

RPG Maker MV/MZ 的游戏目录通常包含：

```text
Game.exe
www/
  index.html
  js/
  data/
  img/
  audio/
```

Android 上可以尝试：

- 直接用 WebView 加载 `www/index.html`。
- 注入 JavaScript 桥接代码，实现金币、变量、开关、物品、传送、速度等控制。
- 在 WebView 上方覆盖虚拟按键和工具面板。

这是 Android 版最适合优先做的引擎。

### 4.2 Ren'Py

Ren'Py Windows 游戏不能直接在 Android 原生运行。

可行路线：

- 工具负责提取、翻译、生成 `game/tl/schinese`。
- 用户或工具引导 Ren'Py Android 打包。
- 如果只有 Windows exe，运行需要 Winlator。

第一版 Android 可以先支持：

- 选择 Ren'Py 游戏目录。
- 提取文本。
- AI 翻译。
- 生成翻译补丁。
- 导出补丁包。

运行与实时修改建议放到第二阶段。

### 4.3 普通 exe 游戏

Android 原生不能直接运行 exe。

可行路线：

- 检测到 exe 后提示用户需要安装 Winlator。
- 保存 exe 路径或游戏目录路径。
- 通过 Intent 或文档引导用户在 Winlator 中打开。
- 工具面板作为悬浮窗显示在 Winlator 上方。

这部分风险最高，因为不同手机、Android 版本、Winlator 版本行为不同。

## 5. 自定义按钮与摇杆

Android 版需要单独做一个输入布局系统。

按钮数据结构建议：

```json
{
  "profileName": "默认 RPG Maker 布局",
  "buttons": [
    {
      "id": "ok",
      "label": "确认",
      "type": "key",
      "key": "Enter",
      "x": 0.82,
      "y": 0.72,
      "size": 0.12,
      "opacity": 0.65
    },
    {
      "id": "cancel",
      "label": "取消",
      "type": "key",
      "key": "Escape",
      "x": 0.68,
      "y": 0.78,
      "size": 0.10,
      "opacity": 0.65
    }
  ],
  "joysticks": [
    {
      "id": "move",
      "x": 0.18,
      "y": 0.76,
      "radius": 0.16,
      "mode": "dpad"
    }
  ]
}
```

需要支持：

- 长按进入编辑模式。
- 拖动按钮改变位置。
- 双指缩放按钮大小。
- 滑块调整透明度。
- 保存为布局方案。
- 针对 RPG Maker、Ren'Py、Winlator 分别保存布局。

## 6. 分阶段实施计划

### 阶段 0：技术验证

目标：先证明 Android 路线可行，不动大规模业务逻辑。

任务：

- 新建 `android_app/` 目录。
- 做一个最小 Android WebView 壳。
- 做一个最小本地 API 服务。
- 手机上打开 UI，能选择目录并返回路径。
- 验证能读取 RPG Maker MV/MZ 的 `www/data/System.json`。
- 验证 WebView 能打开 RPG Maker 的 `www/index.html`。

预计时间：2 到 4 天。

### 阶段 1：核心逻辑解耦

目标：把 `toolkit/app.py` 中的业务逻辑拆出来。

任务：

- 新建 `toolkit/core/`。
- 提取 `ProjectCore`。
- 提取 `TranslationCore`。
- 提取 `RpgMakerCore`。
- 提取 `RenPyCore`。
- 提取 `RuntimeCore`。
- 保证 Windows 版 UI 仍然可以调用这些核心类。

预计时间：7 到 14 天。

### 阶段 2：本地 API

目标：让 Windows UI 和 Android UI 都可以通过同一套核心 API 调用功能。

任务：

- 新建 `toolkit/api/`。
- 提供项目加载、翻译、数据编辑、地图、实时控制接口。
- 长任务全部变成 Job。
- 翻译、嵌入、文本提取都返回进度，不阻塞界面。

预计时间：4 到 7 天。

### 阶段 3：移动端 UI

目标：做一个真正适合手机触控的界面，而不是把桌面界面缩小。

任务：

- 新建 Vue 3 移动端项目。
- 首页支持选择游戏目录。
- 翻译工作台支持移动端列表、筛选、批量翻译。
- 数据编辑器支持卡片式编辑。
- 地图查看支持双指缩放、拖拽、点击格子。
- 实时控制界面改为悬浮抽屉。
- 做按键布局编辑器。

预计时间：10 到 15 天。

### 阶段 4：RPG Maker Android 运行

目标：优先让 RPG Maker MV/MZ 能在手机 WebView 中运行，并接入工具面板。

任务：

- WebView 加载 `www/index.html`。
- 注入 RPG Maker bridge JS。
- 实时读取金币、变量、开关、物品、角色状态。
- 支持传送、穿墙、加速、战斗操作。
- 支持虚拟摇杆和按钮发送输入。

预计时间：7 到 12 天。

### 阶段 5：Ren'Py 与 exe 兼容

目标：把 Ren'Py 和 exe 的 Android 支持分层处理。

Ren'Py：

- 支持提取、翻译、生成补丁。
- 支持引导用户导出 Android 包。
- 后续再研究运行中实时补丁。

exe：

- 接入 Winlator 使用说明。
- 检测 Winlator 是否安装。
- 支持从工具里打开外部运行器。
- 悬浮工具面板覆盖在外部运行器上方。

预计时间：不固定，取决于外部运行器兼容性。

## 7. 风险点

最高风险：

- Android 上直接运行 exe 不现实，必须依赖 Winlator/Wine。
- 悬浮窗和模拟输入在 Android 上会受权限限制。
- Android 11 以后文件访问限制很严格，必须认真处理 SAF。
- 不同 RPG Maker 游戏插件差异大，WebView 运行可能遇到音频、路径、大小写问题。

中等风险：

- 当前 `toolkit/app.py` 很大，拆核心逻辑需要耐心。
- 翻译、嵌入、提取不能阻塞 UI，必须统一 Job 化。
- Ren'Py 的运行时控制不如 RPG Maker MV/MZ 容易。

低风险：

- AI 翻译渠道可以复用。
- 文本缓存、去重、翻译文件管理可以复用。
- RPG Maker 数据 JSON 解析可以复用。

## 8. 建议优先级

第一优先级：

- 不要先追求所有 exe 都能跑。
- 先让 RPG Maker MV/MZ 在 Android WebView 中跑起来。
- 先让翻译、数据查看、地图查看、按键布局可用。

第二优先级：

- 做悬浮作弊面板。
- 做实时桥。
- 做 Winlator 辅助启动。

第三优先级：

- Ren'Py Android 打包辅助。
- Ren'Py 运行中实时替换。
- 更深层的 exe 自动化控制。

## 9. 第一轮我建议真正开始做的内容

下一步建议不是直接写完整 APK，而是先做一个最小可运行原型：

```text
android_app/
  README.md
  mobile_ui/
  backend/
  shell/
```

第一轮验收标准：

- 手机上的 APK 可以打开。
- 可以选择一个 RPG Maker MV/MZ 游戏目录。
- 可以识别 `www/data/System.json`。
- 可以列出游戏名、地图数量、物品数量。
- 可以打开移动端界面。
- 如果是 RPG Maker MV/MZ，可以尝试 WebView 启动 `www/index.html`。

这个原型完成后，再开始把现有 Windows 版的翻译、数据编辑、实时控制逐步迁移进去。

## 10. 不建议做的事情

不建议：

- 直接把 `RPGRenPyLocalizer.exe` 塞进 APK。
- 直接把 tkinter 项目转 Kivy。
- 一上来就支持所有 exe 游戏运行。
- 一上来就做完整悬浮窗作弊面板。
- 把 Windows 版和 Android 版写成两套完全独立逻辑。

建议：

- Windows UI 保留。
- 核心逻辑抽出来。
- Android UI 重新设计。
- 两端共用同一套核心。
- RPG Maker MV/MZ 先做深，Ren'Py 和 exe 后做兼容。


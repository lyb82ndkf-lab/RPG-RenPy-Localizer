# RPGRenPyLocalizer Android / APK 迁移规划

这份规划用于把现有 Windows 版 `RPGRenPyLocalizer` 迁移到 Android。
核心原则只有一个：

- `RPGRenPyLocalizer` 是主体
- Winlator 只是参考开源项目，用来借鉴“游戏运行能力”的实现思路
- 不反过来让 Winlator 成为主壳

## 1. 目标

Android 版要保留现有中文界面和工作流，继续提供：

- 游戏库
- 翻译工作台
- 数据编辑器
- 地图查看
- 存档管理
- 作弊/实时控制
- 虚拟按键/摇杆
- AI 翻译设置

同时补上 Android 上更自然的体验：

- SAF 文件夹选择
- 横屏优先
- 触屏按钮与摇杆布局编辑
- 悬浮工具栏
- 本地缓存与自动备份

## 2. 技术路线

### 主体架构

```text
RPGRenPyLocalizer (主体)
├── Windows 版：保留现有 tkinter 工具
├── Android 版：WebView + Kotlin 壳 + 本地 API
├── 核心逻辑：文本提取 / 翻译 / 数据解析 / 存档处理
└── 运行层适配：RPG Maker / Ren'Py / 外部运行器
```

### Winlator 的位置

Winlator 只用于参考这些能力：

- 容器/运行器管理
- Wine/Box64 启动方式
- 输入映射
- 运行中悬浮工具栏

这些能力如果要接入，也应当以 `RPGRenPyLocalizer` 的 Android 壳为入口。

## 3. Android 版分层

### 3.1 核心层

把 Python 业务拆成可复用核心：

- `project_core`
- `translation_core`
- `rpgmaker_core`
- `renpy_core`
- `runtime_core`
- `save_core`

核心层只处理业务，不依赖 tkinter。

### 3.2 本地 API 层

Android UI 不直接调用复杂 Python 对象，而是走本地 API：

- `POST /api/project/load`
- `GET /api/project/current`
- `GET /api/translate/entries`
- `POST /api/translate/start`
- `POST /api/data/item/update`
- `GET /api/runtime/state`
- `POST /api/runtime/command`
- `GET /api/maps`

### 3.3 Android UI 层

Android 前端建议继续用 Vue 3 / WebView：

- 游戏库
- 翻译工作台
- 数据编辑器
- 地图查看
- 实时控制
- 虚拟按键
- 设置页

### 3.4 Android 壳层

Kotlin 壳负责：

- 申请文件权限
- 读取游戏目录
- 启动 WebView
- 管理悬浮工具栏
- 管理虚拟输入
- 对接本地 Python 服务

## 4. 游戏运行策略

### RPG Maker MV/MZ

优先级最高：

- 先保证 WebView / 本地资源加载
- 再做运行中实时控制
- 再做翻译注入、地图、数据、作弊面板

### Ren'Py

优先级第二：

- 先做文本提取、导入导出、翻译回写
- 再做运行时补丁
- 再考虑更深层的运行中控制

### Windows exe

Android 上不能原生运行 `.exe`，只能：

- 交给 Winlator / Wine / 兼容层
- 或者作为外部运行器方式接入

这部分不做成主路径。

## 5. Android 版最终目标

最终 Android 版应该长这样：

- 主界面还是 `RPGRenPyLocalizer`
- 游戏库导入后可识别引擎
- RPG Maker 游戏优先进入 WebView 运行和实时控制
- Ren'Py 游戏优先进入翻译和补丁流程
- 外部 `exe` 只作为兼容入口，不影响主结构

## 6. 分阶段计划

### Phase 0

验证 Android 壳可用：

- 目录选择
- 本地 API 启动
- WebView 页面加载
- SAF 读写

### Phase 1

拆分 Windows 版核心逻辑：

- 项目识别
- 文本提取
- 翻译队列
- 数据解析
- 存档备份

### Phase 2

做 Android 主界面：

- 游戏库
- 翻译
- 数据
- 地图
- 实时控制
- 虚拟按键

### Phase 3

再考虑外部运行器兼容：

- Winlator
- Wine
- 其他兼容层

## 7. 本项目原则

- 不把 Winlator 当主工程
- 不把 Windows exe 当 Android 主路径
- 先做 `RPGRenPyLocalizer` 自己的主体能力
- 能复用的地方才参考 Winlator


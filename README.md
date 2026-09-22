# RPGRenPyLocalizer

面向 Windows 单机游戏的本地化工作台。它将游戏检测、文本提取、翻译编辑、导出与写回聚合到一个桌面应用中，也可在 Android 端完成翻译与联动操作。

- 桌面端：Electron + Vue 3 + Python 本地服务
- 移动端：Android Shell + 内嵌 WebUI（可与 PC 局域网联动）
- 处理原则：在游戏目录旁创建隔离副本，保留原始文件与可回滚的翻译数据

## 主要功能

### 游戏识别与启动

- 支持从游戏启动 `.exe` 或项目目录自动识别引擎类型
- 游戏库管理：添加、筛选、启动、移除、重新载入
- 运行中状态保护：游戏未退出前禁止切换其他项目，避免工作区串线
- 游戏被移动或删除后给出可读提示，可选择从游戏库移除失效记录

### 多引擎文本提取与翻译

覆盖常见单机与视觉小说相关格式，例如：

| 类型 | 检测与提取范围 | 写回方式 |
| --- | --- | --- |
| RPG Maker MV/MZ | 数据库、对话等安全文本 | 隔离副本 / 运行时翻译表 |
| Ren'Py | 对话、选项、脚本文本 | 翻译包 / 实时 Hook |
| Wolf RPG Editor | `Data` / `BasicData` 与 MTool 翻译 JSON | 带 `translation` 字段的副本文件 |
| Unity | Localization CSV/TSV、String Table、Polyglot 等 | 保持 key 与目标语言字段的翻译副本 |
| Unreal Engine 4/5 | `Content/Localization` archive JSON | 保留 Source / Translation 结构 |
| Galgame / Visual Novel | Kirikiri/KAG、NScripter/ONScripter、GalTransl 等 | 对白写入对应翻译字段 |
| 其他 | Bakin、SRPG Studio、TyranoScript、RGSS 等 | 引擎对应翻译文件与即玩补丁 |

翻译工作台支持：

- 按来源文件、分类、翻译状态筛选
- 搜索、分页、详情编辑、导入/导出翻译包
- 翻译预检：覆盖率、缺失条目、写回定位
- 控制符与占位符保护（如 `\N[1]`、`{player}`、`${value}`、`%s`、HTML/引擎标记）
- 安全翻译范围：RPG Maker 优先处理 `database` / `dialogue`；Ren'Py 优先处理对话与选项，降低误改脚本导致崩溃的风险

### AI 批量翻译

- 按 `entry_id` 的 JSON 协议发送与写回，避免顺序错位
- 支持 OpenAI 兼容接口、Anthropic 兼容接口、Ollama 本地模型
- 可配置批量大小、并发、请求间隔、429 重试、超时与目标语言
- 支持命名保存 / 打开 / 删除多套 AI 配置，以及独立“测试翻译”
- 批译进度、成功/失败数量与错误提示可见

### Ren'Py 实时翻译

- 安装 `zz_rpgrtl_live_bridge.rpy` 捕获对话、菜单与文本组件内容
- 本地 HTTP 桥接异步调用 AI，译文写入缓存并通知游戏刷新
- 保留控制标记顺序，过滤可能导致渲染异常的字体标签
- 支持队列、批量持久化与项目隔离

### RPG Maker 工具

- 地图浏览：拖拽、滚动、格子高亮、事件格点击查看
- 事件详情：事件页、触发方式、出现条件与指令（事件脚本不进入普通批译写回）
- 数据修改：物品、装备、武器、开关、变量、角色等
- 存档修改：金钱、物品、角色等级等；写入前自动安全快照，支持回滚
- 运行时辅助：穿墙、无敌、经验倍率、传送等（视游戏与桥接兼容性）
- 解卡工具：清除卡死图片、重置天气滤镜、处理阻塞事件等应急操作

### 游戏数值修改（CE 简化流程）

1. 选择游戏进程，输入当前数值，执行首次搜索
2. 数值变化后继续筛选
3. 从候选地址写入新值

### MTool 即玩补丁联动

- 自动探测本机 MTool 安装与 loaders
- 为 Bakin、Wolf RPG、SRPG Studio、TyranoScript、Kirikiri、RGSS 等生成标准 `翻译文件.json`、引擎配置与即玩/还原脚本

### Android 端

- 游戏库、翻译工作台、AI 设置、数据与游戏内工具
- RPG Maker MV/MZ 优先内置 WebView 运行；Windows exe 或需兼容层的项目可走兼容运行器
- 横屏游戏态集中展示实时修改、数据库统计与快捷操作，减少对画面的遮挡
- PC Link：局域网连接测试、翻译字典拉取/推送、远程生成即玩补丁

## 安装

### PC 端（Windows）

1. 打开 [Releases](https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/releases)
2. 下载最新的 Setup 安装包或 Portable 便携版
3. 安装或解压后启动；发布版已包含 Python 后端，无需单独安装 Python / Node.js

### Android 端

1. 从 Releases 下载 APK 并安装
2. RPG Maker 项目优先选择 WebView 启动；需 Windows 环境的项目再使用兼容运行器

## 快速使用

### PC 端添加游戏

1. 进入「游戏库」，添加并选择游戏启动 `.exe`（不要只选文件夹）
2. 等待引擎识别后选中该游戏
3. 进入翻译、AI 设置或对应工具页

### 推荐翻译流程（RPG Maker）

1. 载入游戏并确认引擎类型
2. 在「翻译」页提取 `database` / `dialogue`
3. 在「AI 设置」配置渠道并测试翻译
4. 批量翻译 → 检查并保存 → 生成运行时翻译表
5. 从游戏库完整启动游戏查看效果

### 推荐实时流程（Ren'Py）

1. 添加并选择 Ren'Py 游戏
2. 配置并测试 AI 渠道
3. 启动游戏进入内容
4. 回到工具启动「实时翻译」（自动准备 Hook 与本地桥接）

## 配置与数据位置

| 内容 | 位置 |
| --- | --- |
| AI 渠道、模型、密钥与批译参数 | `%APPDATA%\RPGRenPyLocalizer\settings.json` |
| 全局翻译记忆 | `%APPDATA%\RPGRenPyLocalizer\translation_memory.json` |
| 项目工作区与实时缓存 | `<游戏目录>\.rpgrtl_workspace\` |
| 自动备份 | `<游戏目录>\.rpgrtl_backup\` |
| Ren'Py 实时 Hook | `<游戏目录>\game\zz_rpgrtl_live_bridge.rpy` |

API Key 仅保存在本机配置中，请勿提交到 Git、截图或问题反馈。

## 从源码运行与构建

要求：Windows、Python 3.11+、Node.js 20+、npm；Android 另需 Java 17+、Gradle 9.5+。

### PC 桌面端

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pyinstaller
npm install

npm run build:renderer
npm start

# 构建 Windows 安装包（Setup + Portable）
powershell -ExecutionPolicy Bypass -File .\build_electron_release.ps1
```

输出目录：`release-electron/`

### Android 端

```powershell
cd android_app\mobile_ui_src
npm install
npm run build

cd ..\..
powershell -ExecutionPolicy Bypass -File .\build_all.ps1 -Debug
```

输出目录：`dist\android\latest\`

更多桌面打包说明见 [ELECTRON_README.md](./ELECTRON_README.md)。

## 项目结构

```text
RPGRenPyLocalizer/
├── electron/                 # Electron 主进程、preload 与 Vue 前端
├── toolkit/                  # Python 核心：检测、提取、写回、AI、工作区
│   └── api/server.py         # 本地 HTTP API
├── android_app/              # Android Shell、移动端 WebUI、构建脚本
├── tests/                    # 后端回归测试
├── api_server_entry.py       # 打包后端入口
├── build_electron_release.ps1
└── package.json
```

## 反馈

- Issues：https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/issues
- Releases：https://github.com/lyb82ndkf-lab/RPG-RenPy-Localizer/releases
- 邮件：lyb82ndkf@gmail.com

提交问题时请附上工具版本、游戏引擎、复现步骤和已脱敏的错误信息。请勿上传游戏本体、付费资源、API Key 或包含个人信息的存档。

# RPG Maker / Ren'Py 本地化工具箱

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

一个面向 Windows 的单机游戏本地化与数据编辑工具，专注于 RPG Maker 和 Ren'Py 引擎游戏的汉化工作。

## 功能特性

### 核心功能

- **汉化文本提取与回写** - 从游戏文件中提取需要翻译的文本，翻译后写回游戏
- **翻译包导入导出** - 支持 JSON 格式的翻译包，方便协作和版本管理
- **数据库编辑** - 直接编辑游戏数据库中的常见字段
- **对白文本编辑** - 支持 RPG Maker 事件文本和 Ren'Py 对白的直接编辑

### 界面功能

- **现代化桌面界面** - 基于 Python 标准库 tkinter，无需额外安装 GUI 依赖
- **游戏库管理** - 以工作台形式长期管理多个游戏项目
  - 维护常用项目列表
  - 保存备注与标签
  - 查看最近任务
  - 快速载入/打开目录/移除项目
  - 一键启动游戏
- **项目自动识别** - 自动检测游戏引擎类型
- **翻译工作台** - 完整的翻译工作流程
  - 提取文本
  - 导出 JSON 翻译包
  - 导入 JSON 翻译包
  - 逐条编辑译文
  - 回写到游戏
- **环境与备份管理** - 自动环境准备和备份管理

## 支持的游戏引擎

### RPG Maker MV/MZ ✅

- 识别 `data/*.json` 和 `www/data/*.json`
- 提取常见数据库文本
- 提取地图事件/公共事件文本
- 回写翻译内容
- 编辑常见文本字段

### Ren'Py ✅

- 识别 `game/**/*.rpy` 源码文件
- 识别 `game/tl/**` 翻译文件
- 提取对白与字符串
- 生成 `game/tl/schinese/codex_generated.rpy` 翻译文件
- 直接编辑源码对白行

### RPG Maker XP/VX/VX Ace 🚧

- 当前可识别项目目录
- 可加入游戏库管理
- 可一键启动 `Game.exe`
- 完整文本提取与数据编辑功能开发中

## 安装与运行

### 方式一：双击启动（推荐）

直接双击项目根目录下的 `启动工具.bat` 文件。

### 方式二：命令行运行

```bash
# 确保已安装 Python 3.8+
py main.py

# 或者使用 python 命令
python main.py
```

### 环境说明

本工具基于 Python 标准库 `tkinter` 构建 GUI 界面，**无需额外安装第三方包**即可运行主界面。

工具内置了"自动准备环境"功能，会在项目目录下创建 `.venv` 虚拟环境，用于支持：

- 机翻 API 集成
- OCR 文字识别
- 打包成独立 exe 文件
- 更多引擎支持

## 使用指南

### 首次使用

1. 双击 `启动工具.bat` 或运行 `py main.py`
2. 启动器会自动检查并准备运行环境
3. 进入主界面后，点击"添加项目"选择游戏目录
4. 工具会自动识别游戏引擎类型

### 翻译工作流程

1. 在游戏库中选择目标项目
2. 进入"翻译工作台"
3. 点击"提取文本"获取需要翻译的内容
4. 导出 JSON 翻译包进行翻译
5. 导入翻译后的 JSON 包
6. 点击"回写到游戏"完成汉化

### 数据编辑

- **RPG Maker**: 编辑数据库字段、事件文本
- **Ren'Py**: 直接编辑源码中的对白行

## 项目结构

```
RPGRenPyLocalizer/
├── main.py              # 主程序入口
├── launcher.py          # 启动器（带环境准备）
├── 启动工具.bat          # Windows 批处理启动脚本
├── toolkit/             # 核心工具包
│   ├── app.py           # 应用主逻辑
│   ├── detectors.py     # 游戏引擎检测器
│   ├── models.py        # 数据模型
│   ├── renpy.py         # Ren'Py 引擎支持
│   ├── rpgmaker.py      # RPG Maker 引擎支持
│   ├── storage.py       # 数据存储
│   └── workspace.py     # 工作区管理
├── build/               # 构建输出目录
├── dist/                # 分发目录
└── .venv/               # Python 虚拟环境（自动创建）
```

## 备份机制

首次写回或保存修改前，工具会自动在项目根目录创建 `.rpgrtl_backup` 备份目录，确保原始文件安全。

## 当前限制

- 暂未完整支持 RPG Maker VX Ace/XP/2000/2003
- 暂未支持加密封包直接编辑
- 暂未内置自动机翻 API
- 暂未打包为单文件 exe

## 参考来源

本工具的产品方向参考了以下开源项目：

- `2R-Tools-main`
- `RPGMakerUtils-main`
- `RPGMaker2k3VarInspector-master`

当前实现为全新 Python 桌面版本，便于在现有环境里直接运行并持续扩展。

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 更新日志

### v1.0.0

- 初始版本发布
- 支持 RPG Maker MV/MZ 文本提取与回写
- 支持 Ren'Py 对白提取与翻译
- 现代化桌面界面
- 游戏库管理功能
- 自动环境准备

---

**提示**: 本工具仅用于合法的游戏本地化工作，请遵守相关游戏的使用条款和版权规定。

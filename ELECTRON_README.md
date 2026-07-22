# Electron 版说明

本项目现在同时保留原 Python/Tkinter 入口，并新增 Electron 桌面壳。

## 架构

- Electron：负责现代化桌面界面、文件选择、窗口和安装包。
- Python API：`toolkit/api/server.py`，用本地 HTTP JSON API 调用现有 `toolkit.rpgmaker`、`toolkit.renpy` 核心能力。
- 打包：PyInstaller 打包 Python 后端，electron-builder 打包前端和后端到同一个 Windows 程序/安装包。

## 开发启动

```powershell
npm install
npm start
```

Electron 启动后会自动运行：

```powershell
python -m toolkit.api.server --port 0
```

## 构建安装包

```powershell
powershell -ExecutionPolicy Bypass -File .\build_electron_release.ps1
```

输出目录：

```text
release-electron/
├─ RPGRenPyLocalizer Setup 0.2.0.exe   # 标准安装包
├─ RPGRenPyLocalizer 0.2.0.exe         # 可选 portable 单 exe（运行 npm run portable 生成）
└─ win-unpacked/                       # 目录版，可直接运行 RPGRenPyLocalizer.exe
```

如只想生成目录版用于测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_electron_release.ps1 -SkipNpmInstall -DirOnly
```

如只想生成免安装单 exe：

```powershell
npm run portable
```

## 已接入的接口

- 项目识别/载入/启动游戏
- 文本提取、搜索、编辑、导入/导出翻译包、永久写入、运行时补丁；RPG Maker 仅处理 database/dialogue
- AI 翻译：OpenAI 兼容接口、Anthropic 兼容接口、Ollama 本地模型
- RPG Maker 数据记录查看和写入
- RPG Maker 存档槽读取、金钱/物品/角色等级修改和写回；开关、变量在数据修改页实时操作
- RPG Maker 地图列表、地图详情、事件绘制
- RPG Maker/Ren'Py 实时桥接自动准备、启动/停止、状态、刷新、手动写入实时译文
- Ren'Py 实时运行时提取、脚本恢复与安全文本替换

## 注意

新界面调用的是现有 Python 核心逻辑，因此底层能力与旧工具一致；旧 `main.py` / `launcher.py` 仍可继续运行，方便回退。

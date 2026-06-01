# Android Shell

这里是 RPGRenPyLocalizer 的 Android 原生壳工程。它的目标不是把 Windows Tkinter 程序硬搬到手机，而是用 WebView 承载同一套移动工作台界面，再逐步接入游戏运行、翻译、数据查看和实时控制能力。

## 当前能力

- 最小 Gradle Android 工程。
- WebView Activity，启动后加载 `file:///android_asset/mobile_ui/index.html`。
- 构建时自动同步 `../mobile_ui` 到 `assets/mobile_ui`。
- JS Bridge：`window.RPGRenPyShell.pickGameFolder()`。
- JS Bridge：`window.RPGRenPyShell.launchSelectedGame()`。
- JS Bridge：`window.RPGRenPyShell.launchRenpyGame()`。
- JS Bridge：`window.RPGRenPyShell.launchExeWithExternalRunner()`。
- JS Bridge：`window.RPGRenPyShell.openOverlaySettings()`。
- Android SAF 目录选择器入口，并持久化最近选择的目录 URI。
- RPG Maker MV/MZ 运行入口：复制所选目录到 App 缓存，再打开 `www/index.html` 或 `index.html`。
- Ren'Py 运行入口：优先寻找 Ren'Py Web build 的 `index.html`；如果只有 Windows 版 `.exe`，则交给外部兼容运行器。
- Windows `exe` 外部运行入口：在所选目录中递归寻找第一个 `.exe`，然后交给手机上已安装的兼容运行器打开。
- 工具页和游戏页切换按钮。
- 固定比例桌面工作台缩放适配，手机建议横屏使用。
- 横屏优先：Activity 使用 `sensorLandscape`。
- 触屏按键覆盖层：读取移动工作台保存的按键布局，并在游戏画面上生成原生按钮。
- RPG Maker MV/MZ 存档补丁：游戏页加载后尝试把本地存档改为 `localStorage`，避免 Android WebView 文件写入限制。

## 关于手机运行 exe

Android 不能原生执行 Windows `Game.exe`。如果某些工具能在手机上打开 `exe` 游戏，通常是通过下列方案之一实现：

- 使用 RPG Maker / Ren'Py 的移动运行器或引擎适配层。
- 使用 Wine / Winlator / ExaGear 一类 Windows 兼容层。
- 使用工具自带的 Android runtime。

因此当前壳层采用两条路并存：

- RPG Maker MV/MZ：优先尝试直接打开游戏目录里的 `www/index.html`，适合标准 MV/MZ Web 游戏结构。
- Ren'Py：如果游戏已经是 Ren'Py Web build，可以尝试直接用 WebView 打开 `index.html`。如果只是 Windows 发行版，Android 不能直接运行，需要用 Ren'Py Launcher/RAPT 在电脑上重新打包成 APK，或交给外部兼容运行器。
- Windows exe：不假装自己能直接执行，而是把 `.exe` URI 交给 JoiPlay、Winlator、MTool Android 或其他兼容运行器。

## 下一步

- 在 Android 壳内启动本地 Python/Chaquopy 服务，复用桌面端提取、翻译、缓存和数据解析逻辑。
- 为 SAF `content://` 文件树补完整读取适配，减少复制整个游戏目录的等待时间。
- 增加系统级悬浮工具层 Overlay，用于在外部运行器或兼容层游戏上方打开同样的作弊/翻译/数据界面。
- 增加摇杆组件、按键布局导入导出和多套按键配置。
- 为 Ren'Py 增加移动端脚本提取和注入流程。
- 研究 Winlator / JoiPlay 是否提供稳定 Intent 或命令入口，如果有，再做更深的一键启动集成。

## 构建

需要本机已经安装 Android SDK，并准备 Gradle 或 Gradle Wrapper。

```powershell
powershell -ExecutionPolicy Bypass -File .\build_apk.ps1
```

输出位置：

```text
app\build\outputs\apk\debug\app-debug.apk
```

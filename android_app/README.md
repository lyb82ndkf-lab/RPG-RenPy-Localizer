# Android 原型目录

这个目录用于逐步把 `RPGRenPyLocalizer` 迁移成 Android APK。

当前阶段只放规划和骨架，不直接影响 Windows 桌面版。

## 目标

第一版 Android 原型只验证这些事情：

- APK 能打开。
- 能选择手机里的游戏目录。
- 能读取 RPG Maker MV/MZ 的 `www/data/System.json` 或 `data/System.json`。
- 能显示游戏名、地图数量、物品数量。
- 能用 WebView 尝试启动 RPG Maker MV/MZ 的 `www/index.html`。

## 推荐结构

```text
android_app/
  README.md
  backend/
    README.md
  mobile_ui/
    README.md
  shell/
    README.md
```

## 后续技术路线

- `backend/`：放 Python 核心服务，最终复用 `toolkit/core`。
- `mobile_ui/`：放 Vue 3 移动端界面。
- `shell/`：放 Android 壳，负责 WebView、文件权限、悬浮窗、输入映射。

## 当前限制

Android 不能原生运行 Windows `.exe`。如果用户选择的是 exe 游戏，Android 版只能：

- 对 RPG Maker MV/MZ 尝试绕过 exe，直接加载 `www/index.html`。
- 对 Ren'Py 做翻译补丁与打包辅助。
- 对其它 Windows exe 提示使用 Winlator/Wine 运行。


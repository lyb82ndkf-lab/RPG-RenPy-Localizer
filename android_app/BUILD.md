# Android 构建指南 (Material 3 Compose + Winlator)

本文档说明 `RPGRenPyLocalizer` Android 纯原生应用的构建方式与产物架构。

---

## 1. 架构定位

- **UI 框架**：Google 官方 **Jetpack Compose (Material 3)** + **Accompanist**（替代旧版 UniApp / WebView 混合方案）。
- **运行内核**：集成 **Winlator 64 位 ARM 内核**（Wine + Box64 + Turnip/DXVK + XServer），支持免复制直接挂载物理游戏目录并拉起运行。
- **翻译联动**：原生读写 `翻译文件.json` 并内置控制符保护，支持通过局域网 HTTP API 与 PC 端双向无线联动。

---

## 2. 工程结构

```text
android_app/
├── shell/                            # 原生 Android 工程 (Kotlin 2.0 + Compose)
│   ├── app/
│   │   ├── build.gradle              # 模块构建脚本 (配置 Compose 编译器与 M3/Accompanist 依赖)
│   │   └── src/main/
│   │       ├── AndroidManifest.xml   # 清单文件 (配置沉浸式边到边与权限声明)
│   │       ├── jniLibs/arm64-v8a/    # Winlator 64 位核心引擎动态库 (.so)
│   │       └── java/com/rpgrtl/shell/
│   │           ├── MainActivity.kt   # 纯原生 ComponentActivity 入口
│   │           ├── ui/               # Material 3 Compose 界面 (主题/游戏库/工作台/PC联动/容器/设置)
│   │           ├── data/             # 本地游戏持久化与翻译文件管理器
│   │           ├── sync/             # PC 端无线联动客户端
│   │           └── wine/             # Winlator 容器配置与 XServer 渲染窗口
│   └── build_apk.ps1                 # 一键构建打包脚本
└── dist/                             # 最终打包产物输出目录
    └── RPGRenPyLocalizer-v3.3.7-arm64-compose.apk
```

---

## 3. 一键编译与打包

在 Windows PowerShell 下直接运行：

```powershell
cd android_app/shell
.\build_apk.ps1
```

编译输出的 APK 位于：
- `android_app/shell/app/build/outputs/apk/debug/app-debug.apk`
- `android_app/dist/RPGRenPyLocalizer-v3.3.7-arm64-compose.apk`




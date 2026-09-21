# RPGRenPyLocalizer — Android App (Material 3 Compose + Winlator)

基于 **Google 官方 Material3 Compose** 与 **Accompanist** 组件库全面重置的现代化原生 Android 应用。
内核采用 **Winlator 64 位 Wine 兼容层**，深度支持与 PC 端 `RPGRenPyLocalizer` 翻译文件及 API 双向联动。

---

## 核心特性

### 1. 现代化原生 UI (Jetpack Compose)
- **Google 官方 Material3 Compose**：
  - 遵循 **Compose Material 3 Catalog** 现代设计规范，全面支持 Material You 动态色彩（Android 12+ 自适应系统壁纸色调）。
  - 精准现代排版、全套圆角与柔和过渡动画，适配完整深色/浅色模式。
  - 界面风格极致精简专业，剔除冗余说明文本、粗糙边框与杂乱 emoji，打造现代化游戏控制中心。
- **Accompanist 配套组件**：
  - `accompanist-systemuicontroller`: 全面屏边到边沉浸式透明状态栏与导航栏管理。
  - `accompanist-permissions`: Android 13/14+ 存储与媒体权限优雅请求。
  - `accompanist-swiperefresh`: 现代下拉刷新手势交互。

### 2. Winlator 64 位运行内核深度集成
- **ARM64-v8a 高性能架构**：集成 Winlator 原生 prebuilt libraries（`libwinlator.so`、`libvirglrenderer.so`、`libhook_impl.so` 等）。
- **容器与驱动精细化调节**：
  - **Box64 模式**：性能模式 (Performance)、兼容模式 (Compatibility)、安全模式 (Safe)。
  - **图形渲染驱动**：Turnip + DXVK 2.2、Turnip + Zink、VirGL。
  - **分辨率与控制**：支持 1280x720、960x540、1920x1080 预设，内置全套虚拟触摸手柄覆盖层。
- **即玩与盘符挂载**：
  - 采用直接挂载机制，无需跨磁盘复制整个数十 GB 游戏目录。
  - 启动前自动检查并部署 `翻译文件.json`、WolfHook、BakinLauncher 等运行补丁，拉起 `WineDisplayActivity` 进行硬件加速渲染。

### 3. PC 端翻译文件深度联动
- **标准翻译字典格式兼容**：
  - 直接原生读写游戏目录下的 `翻译文件.json`（标准 UTF-8/UTF-8-SIG JSON 字典格式 `{ "原文": "译文" }`）。
- **智能变量控制符防护**：
  - 实时校验 `\V[n]`、`\C[n]`、`[[VAR_...]]`、`{0}`、`%s` 等占位符，防止翻译修改时误删变量导致游戏闪退，并提供“一键自动补齐”。
- **专属 PC 联动中心 (PC Link)**：
  - **连接测试**：自动探测或指定局域网 PC IP 与端口（默认 `35420`）。
  - **一键拉取 (Pull from PC)**：将 PC 端当前打开的游戏翻译字典一键无线拉取至手机，即时保存为本地 `翻译文件.json`。
  - **推送到 PC (Push to PC)**：将手机端编辑好的翻译条目无线回传给 PC 端同步保存。
  - **无线生成即玩补丁**：远程请求 PC 端为当前游戏引擎构建注入补丁包。

---

## 项目架构

```
android_app/shell/app/src/main/java/com/rpgrtl/shell/
├── MainActivity.kt                # 纯原生 ComponentActivity，边到边沉浸与权限引导
├── ui/
│   ├── MainScreen.kt             # 主 Scaffold、M3 NavigationBar 与路由总览
│   ├── theme/                    # Material 3 主题、动态色彩与字体
│   │   ├── Color.kt
│   │   ├── Theme.kt
│   │   └── Type.kt
│   ├── navigation/
│   │   └── NavRoutes.kt          # 5 大导航 Tab (游戏库/工作台/PC联动/容器/设置)
│   ├── library/                  # 游戏库 (卡片流、引擎徽章、一键启动、SAF 导入)
│   │   ├── LibraryScreen.kt
│   │   └── GameDetailSheet.kt
│   ├── workbench/                # 翻译工作台 (单词条卡片、搜索过滤、控制符防护、即时保存)
│   │   ├── TranslationScreen.kt
│   │   └── TranslationItemCard.kt
│   ├── pclink/                   # PC 局域网联动中心 (状态检测、Pull/Push、补丁传输)
│   │   └── PcLinkScreen.kt
│   ├── winlator/                 # Winlator 运行内核管理 (Box64/DXVK/分辨率设置)
│   │   └── WinlatorConfigScreen.kt
│   └── settings/                 # 全局设置 (动态色彩、本地/在线 AI 批量翻译配置)
│       └── SettingsScreen.kt
├── data/
│   ├── model/Models.kt           # 游戏模型、引擎类型枚举、翻译条目模型
│   ├── GameRepository.kt         # 游戏持久化存储与多引擎智能分析探测
│   └── TranslationManager.kt     # 翻译文件读写引擎与控制代码保护器
├── sync/
│   └── PcSyncClient.kt           # 基于 OkHttp/Coroutines 的 PC 端 HTTP 联动客户端
└── wine/                         # Winlator 核心组件与 XServer 渲染 Activity
    ├── WinlatorBridge.kt         # 容器参数封装与 Intent 启动桥
    ├── WineDisplayActivity.kt    # Winlator XServer 渲染窗口与虚拟手柄
    └── ...
```

---

## 构建与运行

### 环境要求
- JDK 17+ (推荐 17 或 21)
- Android SDK (API 34)
- Gradle 8.x / 9.x (推荐 Gradle 9.5.1)

### 本地编译
在 `android_app/shell/` 目录下执行：

```powershell
# 编译 Kotlin 源码
.\gradlew.bat compileDebugKotlin

# 打包 Debug APK
.\build_apk.ps1
```
产物将输出在 `android_app/shell/app/build/outputs/apk/debug/app-debug.apk`。

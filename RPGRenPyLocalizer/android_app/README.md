# RPGRenPyLocalizer — Android App

Android 端 RPG Maker MV/MZ / Ren'Py 翻译与辅助工具。基于 WebView 壳 + UniApp H5 前端。

## 项目结构

```
android_app/
├── backend/                          # Python Flask 服务 (桌面端复用)
│   └── server.py
├── mobile_ui/                        # UniApp H5 编译产物 (自动生成)
│   ├── index.html
│   └── assets/                       # JS/CSS 打包文件
├── shell/                            # Android 原生壳 (Kotlin)
│   ├── app/
│   │   ├── build.gradle
│   │   └── src/main/
│   │       ├── AndroidManifest.xml
│   │       ├── assets/
│   │       │   ├── mobile_ui/        # UniApp 编译产物 (自动复制)
│   │       │   └── scripts/          # 注入脚本 (rpgmv-cheat.js 等)
│   │       ├── java/com/rpgrtl/shell/
│   │       │   ├── MainActivity.kt              # 主 Activity + WebView 管理
│   │       │   ├── AndroidRpgMakerService.kt    # RPG Maker 数据解析
│   │       │   ├── AndroidAiTranslationService.kt # AI 翻译
│   │       │   ├── ShellBridge.kt               # JS→Kotlin 桥接
│   │       │   ├── ShellWebViewClient.kt        # WebView 拦截
│   │       │   └── GameErrorBridge.kt           # JS 错误收集
│   │       └── res/
│   └── build_apk.ps1                 # 一键构建脚本
├── AndroidAPP/                       # UniApp 源码目录
│   └── AndroidAPP/                   # (嵌套的 UniApp 项目)
│       ├── pages.json                # 路由 + Tab 配置
│       ├── manifest.json             # 应用配置 + 权限
│       ├── pages/                    # 页面组件
│       │   ├── index/                # 游戏库 (首页)
│       │   ├── translate/            # 翻译工作台
│       │   ├── data-editor/          # 数据编辑器
│       │   ├── maps/                 # 地图查看器
│       │   ├── saves/                # 存档管理
│       │   ├── settings/             # 设置 + 虚拟按键
│       │   └── runtime/              # 作弊面板 (建设中)
│       ├── components/               # 公共组件
│       │   ├── GameCard.vue
│       │   ├── TranslationItem.vue
│       │   ├── DataTable.vue
│       │   ├── DataEditor.vue
│       │   ├── MapCanvas.vue
│       │   ├── VirtualController.vue
│       │   ├── ControlButton.vue
│       │   └── ...
│       ├── api/                      # API 封装
│       └── store/                    # Pinia 状态管理
├── dist/android/                     # 构建产物输出
│   ├── *-universal-debug.apk         # 通用调试包
│   ├── *-arm64-debug.apk             # arm64 调试包
│   ├── *-armv7-debug.apk             # armeabi-v7a 调试包
│   └── *-release-signed.apk          # 已签名 Release 包
└── README.md
```

## 构建

### 前置条件

- Android Studio (推荐 Hedgehog 2023.1.1+)
- Android SDK (API 34)
- UniApp CLI: `npm install -g @dcloudio/uni-app-cli`
- JDK 17+

### 一键构建

```powershell
cd android_app
.\build_all.ps1 -Version 2.3
```

或手动分步：

```powershell
# 1. 编译 UniApp H5
cd AndroidAPP/AndroidAPP
npx uni-app build --platform h5

# 2. 复制到 shell
Copy-Item -Recurse -Force dist/build/h5/* ../shell/app/src/main/assets/mobile_ui/

# 3. Gradle 打包
cd ../shell
./gradlew assembleDebug    # 或 assembleRelease
```

### APK 产物说明

| 文件名 | 适用设备 | 说明 |
|---|---|---|
| `*-universal-*.apk` | 任何 | 兼容所有架构 |
| `*-arm64-*.apk` | 2020 年后手机 | 体积最小 |
| `*-armv7-*.apk` | 旧款/低端手机 | armeabi-v7a |
| `*-release-signed.apk` | 任何 | 已签名可安装 |

## 核心架构

```
┌─────────────────────────────────────────┐
│  UniApp H5 前端                          │
│  (Vue 3 + Pinia + vue-router)           │
├─────────────────────────────────────────┤
│  Kotlin Shell                           │
│  - WebView 管理 (工具 + 游戏两个实例)     │
│  - SAF 文件索引 + LRU 缓存               │
│  - JS→Kotlin @JavascriptInterface 桥     │
│  - 虚拟按键叠加层 (FrameLayout)          │
│  - 游戏预热加载 + 崩溃恢复               │
├─────────────────────────────────────────┤
│  Android 系统层                          │
│  - Storage Access Framework (SAF)        │
│  - WebView GPU 渲染                      │
│  - System Alert Window (悬浮窗)          │
└─────────────────────────────────────────┘
```

## 已实现的优化

### 性能

- ✅ GPU 合成 + `translateZ(0)` WebView 加速
- ✅ Tab 秒切 — `keep-alive` + `CSS containment`
- ✅ SAF 文件索引 + 10 分钟缓存 + LRU 内容缓存
- ✅ AI 翻译分块处理 (每 20 条一批，不阻塞 UI)
- ✅ 冷启动打点 + FPS 检测 + PERF 日志
- ✅ `onTrimMemory` 内存收放
- ✅ `pauseTimers/resumeTimers` 后台不空转
- ✅ 游戏 WebView 预热 (工具页停留 3 秒后后台预载)
- ✅ 地图 Canvas 位图缓存
- ✅ 数据编辑器输入框尺寸压缩 + 字号优化

### 稳定性

- ✅ `onRenderProcessGone` 崩溃恢复
- ✅ 游戏背景音乐不中断 (GONE→INVISIBLE)
- ✅ WebGL 兼容补丁 (降低黑屏/白屏)
- ✅ JS 错误收集 (GameErrorBridge)
- ✅ R8 + shrinkResources 压缩
- ✅ 横竖屏 configChanges 完整配置

### 用户体验

- ✅ 缩放异常修复 (移除虚假 resize 注入)
- ✅ 数据编辑器左侧显示角色名 (读取 JSON 内 `name` 字段)
- ✅ 虚拟按键坐标对齐 (预览 = 实际位置)
- ✅ APK 签名自动化 (Release 可直接安装)
- ✅ ABI 分包 (arm64 / armeabi-v7a / universal)
- ✅ 构建产物版本归档

## 功能

- **游戏库**: SAF 选择目录 → 自动识别 RPG Maker MV/MZ / Ren'Py
- **翻译工作台**: 搜索 → 编辑 → AI 翻译 (DeepSeek/OpenAI)
- **数据编辑器**: Actors/Items/Weapons/Armors/Classes/States 实时修改
- **地图查看器**: 地图网格 + 事件标记
- **存档管理**: 槽位列表 + 备份 + 编辑
- **虚拟按键**: 可拖拽配置的摇杆/按钮覆盖层
- **作弊引擎** (开发中): 穿墙/传送/战斗控制/属性锁定/加速

## 技术栈

| 层 | 技术 |
|---|---|
| 前端框架 | UniApp (Vue 3) |
| 状态管理 | Pinia |
| 路由 | vue-router 4 (H5 模式) |
| UI 组件 | uni-ui (部分) |
| 安卓壳 | Kotlin + WebView + SAF |
| 构建 | Gradle + Vite |
| 编译目标 | Android 7.0+ (API 24+) |

# Phase 2: RPGTL 主体 + Winlator 引擎参考

## 目标

本阶段纠正集成方向：

- `RPGRenPyLocalizer` 是最终 APK 主体
- Winlator 只作为参考项目
- Android 用户打开后首先看到 RPGTL 中文界面
- 游戏运行能力由 RPGTL 壳层统一封装

## 非目标

本阶段不做这些事情：

- 不把 RPGTL 做成 Winlator 的附属按钮
- 不要求用户先打开 Winlator 再打开工具
- 不把 Winlator 的英文 UI 暴露给用户
- 不让 Winlator 成为主 Activity

## 总体架构

```text
RPGRenPyLocalizer APK
├── UniApp / Vue 中文界面
├── Kotlin Shell
│   ├── SAF 文件访问
│   ├── WebView 游戏运行器
│   ├── 虚拟按键
│   ├── 悬浮工具栏
│   └── Runtime Bridge
├── RPGTL Core
│   ├── 翻译
│   ├── 数据解析
│   ├── 存档备份
│   └── 地图/事件解析
└── 可选运行后端
    ├── RPG Maker WebView 后端
    ├── Ren'Py 翻译/补丁后端
    └── Wine/Winlator 兼容后端
```

## Winlator 可借鉴部分

从 Winlator 阅读和迁移思路，不直接换主壳：

- `ContainerManager`: 容器目录组织方式
- `Launcher`: Wine/Box64 启动流程
- `XServerDisplayActivity`: 游戏画面承载方式
- `inputcontrols`: 虚拟按键和输入映射
- `RootFSInstaller`: 首次环境准备

## Android Shell 新增模块

建议在 `android_app/shell/app/src/main/java/com/rpgrtl/shell/` 下新增：

```text
wine/
├── WineRuntimeEngine.kt
├── WineContainerStore.kt
├── WineGameLauncher.kt
├── WineRuntimeBridge.kt
└── WineGameDetector.kt

overlay/
├── GameToolbarOverlay.kt
├── TouchControlOverlay.kt
└── OverlayLayoutStore.kt
```

这些模块只服务 RPGTL 壳，不依赖 Winlator UI。

## 前端入口

前端继续保持 RPGTL 的中文导航：

```text
游戏库 | 实时控制 | 角色 | 物品 | 武器 | 防具 | 状态 | 翻译 | 地图 | 存档 | 按键
```

游戏库中的启动逻辑：

```text
RPG Maker MV/MZ
  -> 优先用 RPGTL WebView 后端

Ren'Py
  -> 优先用翻译/补丁后端

Windows exe
  -> 可选 Wine/Winlator 兼容后端
```

## Kotlin Bridge

新增对前端暴露的接口：

```kotlin
androidDetectLaunchBackend(gameUri)
androidLaunchGame(gameUri, backend)
androidStopGame()
androidShowGame()
androidShowTool()
androidRuntimeCommand(commandJson)
androidSaveTouchLayout(layoutJson)
androidLoadTouchLayout()
```

旧的 `androidLaunchGameViaWine` 只作为内部实现，不直接暴露成唯一启动方式。

## 实施顺序

1. 保持 RPGTL APK 主界面不变。
2. 修正游戏库启动逻辑，让它根据引擎选择后端。
3. RPG Maker MV/MZ 继续走 WebView 后端。
4. Ren'Py 继续走翻译/补丁后端。
5. Windows exe 才进入 Wine 兼容后端。
6. 从 Winlator 参考实现中提取可复用思路，写成 RPGTL 自己的 Kotlin 模块。

## Winlator 引擎搬迁分析

`_tmp_winlator_app` 中没有一个可以直接复制的单独 `Launcher` 类。真正的启动链是：

```text
XServerDisplayActivity
  -> RootFS / RootFSInstaller
  -> ContainerManager / Container
  -> XServer / XServerView / GLRenderer
  -> XEnvironment
     -> SysVSharedMemoryComponent
     -> XServerComponent
     -> NetworkInfoUpdateComponent
     -> ALSAServerComponent 或 PulseAudioComponent
     -> VirGLRendererComponent 或 VortekRendererComponent
     -> GuestProgramLauncherComponent
        -> box64 + wine explorer /desktop=...
```

因此不能简单把 `Launcher.java` 搬过来，因为当前源码里根本不是这个结构。正确做法是：

1. 在 RPGTL 里保留 `com.rpgrtl.shell.MainActivity` 作为主入口。
2. 在同一个 APK 中新增一个内部 `WineDisplayActivity`。
3. `WineDisplayActivity` 只做运行游戏所需的最小 UI：`XServerView + Touchpad/Input overlay + RPGTL 工具按钮`。
4. Winlator 引擎相关类保持 `com.winlator.*` 包名，避免 JNI 函数名全部失效。
5. RPGTL 前端调用 `androidLaunchGame("wine")` 时，由 `MainActivity` 启动内部 `WineDisplayActivity`。

### 必搬模块

这些是 Wine/Box64 运行闭包，第一批需要搬：

```text
app/src/main/java/com/winlator/container/
app/src/main/java/com/winlator/core/
app/src/main/java/com/winlator/xenvironment/
app/src/main/java/com/winlator/xconnector/
app/src/main/java/com/winlator/xserver/
app/src/main/java/com/winlator/renderer/
app/src/main/java/com/winlator/sysvshm/
app/src/main/java/com/winlator/winhandler/
app/src/main/java/com/winlator/alsaserver/
app/src/main/java/com/winlator/math/
app/src/main/java/com/winlator/widget/XServerView.java
app/src/main/java/com/winlator/widget/TouchpadView.java
app/src/main/java/com/winlator/widget/InputControlsView.java
```

### 必搬 native

JNI 依赖 `com.winlator.*` 包名，建议原样搬：

```text
app/src/main/cpp/winlator/
app/src/main/cpp/gladiorenderer/
app/src/main/cpp/midihandler/
app/src/main/cpp/virglrenderer/
app/src/main/cpp/vortekrenderer/
app/src/main/cpp/libadrenotools/
app/src/main/cpp/CMakeLists.txt
```

`CMakeLists.txt` 可先保留：

```cmake
add_subdirectory(winlator)
add_subdirectory(vortekrenderer)
add_subdirectory(virglrenderer)
add_subdirectory(midihandler)
add_subdirectory(libadrenotools)
add_subdirectory(gladiorenderer)
```

### 必搬 assets

第一版 Wine 后端至少需要：

```text
rootfs.tzst
container_pattern.tzst
common_dlls.json
box64/box64-*.tzst
box64/default.box64rc
box64/env_vars.json
pulseaudio.tzst
graphics_driver/virgl-*.tzst
graphics_driver/zink-*.tzst
dxwrapper/dxvk-*.tzst
wincomponents/*.tzst
```

这会显著增大 APK。后续可以把不常用组件改成首次运行下载。

### Gradle 需求

RPGTL 当前 `android_app/shell/app/build.gradle` 还没有 NDK/CMake 配置。接入 Winlator native 后需要新增：

```groovy
ndkVersion "24.0.8215888"

externalNativeBuild {
    cmake {
        version "3.22.1"
        path "src/main/cpp/CMakeLists.txt"
    }
}

dependencies {
    implementation "androidx.appcompat:appcompat:1.4.0"
    implementation "androidx.preference:preference:1.2.1"
    implementation "com.google.android.material:material:1.4.0"
    implementation "com.github.luben:zstd-jni:1.5.2-3@aar"
    implementation "org.tukaani:xz:1.7"
    implementation "org.apache.commons:commons-compress:1.20"
}
```

### 下一步编码目标

先不要一次性搬完整 Winlator UI。下一步只做“能编译”的引擎骨架：

1. 复制 Winlator 必搬模块到 RPGTL。
2. 保持 `com.winlator.*` 包名。
3. 加入 CMake / jniLibs / assets。
4. 新建 `com.rpgrtl.shell.wine.WineEngineBridge`。
5. 新建 `WineDisplayActivity`，先能打开空白 XServerView。
6. `androidLaunchGame("wine")` 能启动该 Activity。
7. 编译通过后，再接入 `GuestProgramLauncherComponent` 真正启动 exe。

## 验收标准

- 安装 APK 后默认显示 RPGTL 中文界面。
- 游戏库、翻译、数据、地图、存档、作弊、按键仍然是 RPGTL 的界面。
- 点击 RPG Maker MV/MZ 游戏可以从 RPGTL 内启动。
- 游戏运行中能打开 RPGTL 悬浮工具栏。
- 点击工具返回后不重启游戏。
- Windows exe 兼容能力作为后端存在，但不改变主 UI。

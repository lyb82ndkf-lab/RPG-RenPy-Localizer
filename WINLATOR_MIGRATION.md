# Winlator 引擎迁移清单

## 目标

把 Winlator 的 Wine/Box64 兼容引擎搬进 `RPGRenPyLocalizer` 的 Android 壳，让 RPGTL 的 **中文界面** + **游戏库/翻译/数据/作弊** 可以直接启动 Windows exe 游戏，不用切到其他 App。

## 迁移原则

```
1. 只搬 Winlator 引擎层（cpp + jniLibs + assets + 核心 Java）
2. 不搬 Winlator UI 层（Fragment、Dialog、设置、列表）
3. RPGTL 仍然是主 Activity 和中文界面入口
4. WineDisplayActivity 是显示层，接收 RPGTL 的启动命令
5. 分批搬运，每批都能编译通过
```

---

## 第一批：纯 Native + 运行时核心（必搬）

> ⚠️ 修正：`inputcontrols/` 和 `box64/` 不是可选依赖，
> `GuestProgramLauncherComponent` 直接依赖 `Box64Preset` + `Box64PresetManager`，
> 输入链也绑在 `XServerDisplayActivity` 里。所以全部编入第一批。

### 1.1 C++ Native 代码

```
源路径 (_tmp_winlator_app/app/src/main/cpp/)      目标路径 (android_app/shell/app/src/main/cpp/)
────────────────────────────────────────────────────────────────────────────────────────────
winlator/                                          winlator/          ← X11 协议 + 输入
gladiorenderer/                                    gladiorenderer/    ← GL 渲染器
virglrenderer/                                     virglrenderer/     ← VirGL 渲染
vortekrenderer/                                    vortekrenderer/    ← Vulkan 渲染 (Turnip)
libadrenotools/                                    libadrenotools/    ← Adreno GPU 驱动工具
midihandler/                                       midihandler/       ← MIDI 音频
CMakeLists.txt                                     CMakeLists.txt     ← 根 CMake
```

**依赖关系**：这些模块相互独立，可以一次搬完。

### 1.2 JNI 库（.so）

```
源路径 (_tmp_winlator_app/app/src/main/jniLibs/)    目标路径 (android_app/shell/app/src/main/jniLibs/)
────────────────────────────────────────────────────────────────────────────────────────────────
arm64-v8a/libcbox64dyn.so                           arm64-v8a/libcbox64dyn.so     ← Box64 动态库
arm64-v8a/libfnative.so                              arm64-v8a/libfnative.so       ← 兼容层
arm64-v8a/libgl4es.so                                arm64-v8a/libgl4es.so         ← OpenGL ES 包装
arm64-v8a/libpython*.so                              arm64-v8a/libpython*.so       ← Python (Ren'Py)
arm64-v8a/libvulkan.so                               arm64-v8a/libvulkan.so        ← Vulkan 驱动
arm64-v8a/*.so                                       arm64-v8a/*.so               ← 其他全部
armeabi-v7a/                                         armeabi-v7a/                  ← 同上（32位版）
```

**注意**：`jniLibs` 全部复制即可，不涉及代码改动。

### 1.3 资源文件

```
源路径 (_tmp_winlator_app/app/src/main/assets/)      目标路径 (android_app/shell/app/src/main/assets/)
───────────────────────────────────────────────────────────────────────────────────────────────────
rootfs.tzst                                          winlator/rootfs.tzst          ← Wine 容器文件系统
container_pattern.tzst                               winlator/container_pattern.tzst
common_dlls.json                                     winlator/common_dlls.json
box64/                                               winlator/box64/               ← Box64 预设
dxwrapper/                                           winlator/dxwrapper/           ← DirectX 包装
graphics_driver/                                     winlator/graphics_driver/     ← GPU 驱动
wincomponents/                                       winlator/wincomponents/       ← Wine 组件
pulseaudio.tzst                                      winlator/pulseaudio.tzst      ← 音频
inputcontrols/                                       winlator/inputcontrols/       ← 控制预设
soundfont/                                           winlator/soundfont/           ← MIDI 音色
```

### 1.4 Java 运行时核心

```
源路径 (_tmp_winlator_app/app/src/main/java/com/winlator/)    目标包 (com/rpgrtl/engine/)
───────────────────────────────────────────────────────────────────────────────────────────
xenvironment/                                                  xenvironment/      ← 容器环境
├── EnvironmentComponent.java                                   │
├── RootFS.java                                                  │
├── RootFSInstaller.java                                         │
└── components/                                                   │
    ├── ALSAServerComponent.java                                  │
    ├── GuestProgramLauncherComponent.java     ← 核心！启动 Wine  │
    ├── NetworkInfoUpdateComponent.java                          │
    └── ... (其他 Component)                                       │

xserver/                                                       xserver/           ← X11 显示服务器
├── XServer.java                                                 │
├── ClientOpcodes.java                                           │
├── Cursor.java                                                   │
├── Screen.java                                                   │
├── Pixmap.java                                                   │
├── GC.java (GraphicsContext)                                     │
├── Font.java                                                     │
├── Drawable.java                                                 │
├── Window.java                                                   │
├── Property.java                                                 │
├── requests/*.java     ← X11 请求处理                            │
├── events/*.java       ← X11 事件                                │
├── extensions/*.java   ← X11 扩展 (DRI3, BigReq)                 │
└── errors/*.java       ← X11 错误                                │

xconnector/                                                    xconnector/        ← X11 连接层
├── ConnectedClient.java                                          │
├── ConnectionHandler.java                                        │
└── RequestHandler.java                                           │

container/                                                     container/         ← 容器管理
├── Container.java                                                │
├── ContainerManager.java                                         │
├── AudioDrivers.java                                             │
├── GraphicsDriver.java                                           │
├── WineVersion.java                                              │
└── WineContainerResolver.java                                    │

core/                                                          core/             ← 工具类
├── AppUtils.java                                                 │
├── ArrayUtils.java                                               │
├── BatteryUtils.java                                             │
├── Launcher.java          ← 实际启动 Wine+Box64                  │
├── NativeLibsUtils.java                                          │
├── Permissions.java                                              │
├── ProcessHelper.java                                            │
├── ProcessTimeoutHandler.java                                    │
├── ScreenGravity.java                                            │
└── ToastHelper.java                                              │

renderer/                                                      renderer/         ← OpenGL 渲染
├── GLRenderer.java                                               │
├── EffectComposer.java                                           │
├── FullscreenTransformation.java                                 │
├── Renderer.java                                                 │
└── effects/*.java                                                │

sysvshm/                                                       sysvshm/          ← 共享内存
├── SysVSHMConnectionHandler.java                                 │
├── SysVSHMRequestHandler.java                                    │
└── RequestCodes.java                                             │

alsaserver/                                                    alsaserver/       ← 音频
├── ALSAClient.java                                               │
├── ALSAClientConnectionHandler.java                              │
├── ALSARequestHandler.java                                       │
└── RequestCodes.java                                             │

winhandler/                                                    winhandler/       ← 窗口/手柄/键盘
├── GamepadHandler.java                                           │
├── GamepadPlayerConfig.java                                      │
├── MIDIHandler.java                                              │
├── TouchInputHandler.java                                        │
└── WinHandler.java                                               │

inputcontrols/                                                 inputcontrols/    ← 输入控制（必搬！）
├── Binding.java                                                  │
├── ControlElement.java                                           │
├── ControlsProfile.java                                          │
├── InputControlsManager.java                                     │
└── InputDeviceHelper.java                                        │

box64/                                                         box64/            ← Box64 预设（必搬！）
├── Box64Preset.java                                              │
├── Box64PresetManager.java                                       │
└── Box64EditPresetDialog.java                                    │

math/                                                          math/             ← 数学工具
├── Mathf.java                                                    │
└── XForm.java                                                    │

widget/                                                        widget/           ← 显示组件（必搬 3 个）
├── XServerView.java            ← 核心！显示 X11 输出的 SurfaceView   │
├── TouchpadView.java           ← 触摸板                              │
└── InputControlsView.java      ← 输入控制覆盖层                       │
```

---

## 第二批：增量功能（可后搬）

这些不是启动 Winlator 引擎的必需项，但能提升体验：

```
box64/
├── Box64Preset.java
├── Box64PresetManager.java
└── Box64EditPresetDialog.java       ← UI 类，可暂不搬

core/
├── CpuInfo.java                    ← CPU 信息检测（启动时检测，不是必需）
├── DeviceInfo.java                 ← 设备信息
└── ScreenGravity.java              ← 屏幕方向（已有 Unity 自带）

contentdialog/                      ← Winlator 的设置对话框
├── SettingsDialog.java              ← 不搬（RPGTL 有自己的设置页）
├── EditContainerDialog.java         ← 不搬
└── ...                              ← 不搬
```

---

## 第三批：暂不搬运（Winlator UI 层）

```
ContainersFragment.java              ← Winlator 的容器列表（RPGTL 游戏库代替）
ShortcutsFragment.java               ← Winlator 的快捷方式（RPGTL 游戏库代替）
ContainerDetailFragment.java          ← Winlator 容器详情
ContainerFileManagerFragment.java     ← Winlator 文件管理器
BaseFileManagerFragment.java          ← Winlator 文件浏览
SettingsFragment.java                 ← Winlator 设置
XServerDisplayActivity.java           ← Winlator 显示 Activity（RPGTL 的 WineDisplayActivity 代替）
```

---

## 搬运顺序执行清单

### 第 1 步：Native + 资源（纯复制，不用改代码）

```bash
# 1.1 复制 cpp
cp -r _tmp_winlator_app/app/src/main/cpp/* \
      android_app/shell/app/src/main/cpp/

# 1.2 复制 jniLibs
cp -r _tmp_winlator_app/app/src/main/jniLibs/* \
      android_app/shell/app/src/main/jniLibs/

# 1.3 复制 assets（放到 winlator/ 子目录）
mkdir -p android_app/shell/app/src/main/assets/winlator
cp -r _tmp_winlator_app/app/src/main/assets/rootfs.tzst \
      android_app/shell/app/src/main/assets/winlator/
cp -r _tmp_winlator_app/app/src/main/assets/box64 \
      android_app/shell/app/src/main/assets/winlator/
# ...（按清单全部复制）
```

### 第 2 步：改 `app/build.gradle` 加 NDK 编译

```groovy
android {
    externalNativeBuild {
        cmake {
            path "src/main/cpp/CMakeLists.txt"
        }
    }
    // 允许大资源文件
    aaptOptions {
        noCompress 'tzst', 'so', 'dll'
    }
}
```

### 第 3 步：把 Java 核心复制进来 + 改包名

```bash
# 建新包路径
BASE=android_app/shell/app/src/main/java/com/rpgrtl/engine

# 搬运（保持目录结构）
cp -r _tmp_winlator_app/app/src/main/java/com/winlator/xenvironment $BASE/
cp -r _tmp_winlator_app/app/src/main/java/com/winlator/xserver $BASE/
cp -r _tmp_winlator_app/app/src/main/java/com/winlator/container $BASE/
# ...

# 批量改包名（com.winlator.xxx → com.rpgrtl.engine.xxx）
find $BASE -name '*.java' -exec sed -i \
  's/package com\.winlator/package com.rpgrtl.engine/g' {} \;

find $BASE -name '*.java' -exec sed -i \
  's/import com\.winlator/import com.rpgrtl.engine/g' {} \;
```

### 第 4 步：改 `WineDisplayActivity` 为真正显示

```kotlin
// WineDisplayActivity.kt — 从占位页改为真实引擎显示
class WineDisplayActivity : Activity() {
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val gamePath = intent.getStringExtra("gamePath")!!
        val containerId = intent.getStringExtra("containerId")!!
        
        // 创建 XServerView（Winlator 搬来的）
        val xserverView = XServerView(this)
        
        // 初始化引擎
        val engine = WinlatorEngine(this)
        engine.initialize(containerId, xserverView)
        engine.start(gamePath)
        
        setContentView(xserverView)
    }
}
```

### 第 5 步：编译

```bash
cd android_app/shell
./gradlew assembleDebug
```

---

## 验证清单

每完成一步后验证：

| # | 验证项 | 方法 |
|---|---|---|
| 1 | Native 编译通过 | `./gradlew assembleDebug` 不报 CMake 错误 |
| 2 | Engine Java 编译通过 | 无包名/import 错误 |
| 3 | 点击 [▶ 运行] → 进入 WineDisplayActivity | 不崩溃 |
| 4 | XServerView 显示游戏画面 | 看到游戏画面 |
| 5 | 输入可操作游戏 | 触摸/按键有响应 |
| 6 | 浮动工具栏可调出 | Overlay 显示中文工具按钮 |

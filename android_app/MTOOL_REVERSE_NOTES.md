# MTool Android Reverse-Engineering Notes

本文件只记录从 `D:\程序\RPG tool\MTool\_decoded` 中观察到的兼容性结论，用于指导 RPGRenPyLocalizer Android 版的自研实现。不要复制 MTool 的专有代码、资源、签名、native 库或运行时包。

## 样本

- `mtool_v45_1`：通用移动工具包，包含 `libnode.so`、Web/Node 资源、Gecko 相关库、VFS 组件。
- `mtool_renpy_v18_1`：Ren'Py 运行包，包含 Ren'Py/Python Activity、`runtime-pack.tar.zst`、`libmtool_client.so`、VFS 和 Gecko 相关库。
- `mtool_mkxpz_v46_1`：mkxp-z/RGSS 运行包，包含 `libmkxp-z*.so`、Ruby、SDL2、OpenAL、RTP 资源和 VFS 组件。

## 关键结论

- MTool 不是靠一个普通 WebView APK 直接运行所有 Windows `exe`。
- 它按引擎拆分运行时：
  - MV/MZ/工具层：Node/Web/Gecko/VFS。
  - Ren'Py：Python/Ren'Py Android runtime + 打包运行资源。
  - XP/VX/VX Ace/RGSS：mkxp-z + Ruby + SDL2 + RTP。
- 三个 APK 都强调横屏、游戏模式、硬件加速、低延迟音频、常亮、较低 targetSdk、资源不压缩和 native/runtime 解包。
- 文件访问不是单纯依赖普通外部存储权限，而是配合 VFS / FileProvider / 后台服务/运行时资源复制。

## 已落地到本项目

- Android Manifest 增加游戏容器相关能力：
  - `INTERNET`
  - `ACCESS_NETWORK_STATE`
  - `VIBRATE`
  - `WAKE_LOCK`
  - `MODIFY_AUDIO_SETTINGS`
  - `HIGH_SAMPLING_RATE_SENSORS`
  - legacy 读写存储权限
  - 游戏手柄、触屏、横屏、低延迟音频、OpenGL ES 2.0 feature
- Application 增加：
  - `appCategory="game"`
  - `isGame="true"`
  - `hardwareAccelerated="true"`
  - `largeHeap="true"`
  - `extractNativeLibs="true"`
  - `requestLegacyExternalStorage="true"`
- Activity 增加：
  - 横屏传感器
  - 沉浸模式
  - 更完整的 `configChanges`
  - `singleTop`
  - 保持任务状态
  - 最小后处理偏好
- Gradle 增加常见游戏资源 `noCompress`：
  - 音频、图片、Ren'Py 包、RPG Maker/RGSS 包、native 库、压缩运行时。
- MainActivity 增加：
  - 屏幕常亮。
  - 沉浸式隐藏状态栏/导航栏。
  - 生命周期中暂停/恢复 WebView。
  - 原生触屏按键覆盖层。

## 仍需自研/开源替代

- Ren'Py 原生运行：
  - 不能复制 MTool 的 `runtime-pack.tar.zst` 或 `libmtool_client.so`。
  - 应使用 Ren'Py 官方 RAPT/Android runtime 或构建一个可下载/可配置的开源 runtime。
- RGSS/mkxp-z：
  - 不能复制 MTool 的 `libmkxp-z*.so`、Ruby 和 RTP。
  - 可研究 mkxp-z、mkxp、SDL2、OpenAL 的开源 Android 编译链，做独立运行器。
- VFS：
  - MTool 使用了 VFS fd handoff/relay 结构。
  - 我们目前先使用 SAF + 缓存复制；后续可做自己的 ContentProvider/FileProvider 和流式文件访问，减少复制整个游戏目录。
- 外部 exe：
  - Android 不能原生执行 Windows exe。
  - 仍然需要外部兼容运行器，或后续集成开源 Wine/Winlator 类方案。

## 下一步建议

1. 短期：把 MV/MZ WebView 运行做稳，包括存档、音频、触控、横屏、游戏目录复制进度。
2. 中期：接入 Ren'Py 官方 Android 构建/运行链路，优先支持 Ren'Py Web build 和源码项目。
3. 中期：做自己的 FileProvider/VFS-lite，减少大目录复制。
4. 长期：用 mkxp-z 开源链路编译 RGSS Android runtime，支持 XP/VX/VX Ace。
5. 长期：若确实要“手机运行 Windows exe”，需要独立研究 Wine/Winlator 集成，而不是把普通 APK 当 exe 解释器。

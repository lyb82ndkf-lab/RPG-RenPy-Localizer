# Android Build Plan

这是 `RPGRenPyLocalizer` 的 Android / APK 入口说明。

当前状态：

- `backend/` 已经有 Python 原型服务。
- `mobile_ui/` 已经有可在浏览器预览的手机端界面。
- `shell/` 还只是计划层，没有真正的原生 Android 工程。

## 下一步目标

把下面这套结构落地成真正的 APK 工程：

```text
android_app/
  backend/          # Python 核心服务
  mobile_ui/        # Vue 或静态 UI
  shell/            # Android 壳
  build/            # 构建缓存
```

## 推荐实现方式

### 方案 A

Kotlin + WebView + 本地 Python 服务

- 更适合长期维护。
- 可以直接做文件选择、悬浮窗、权限、Intent。
- UI 放 WebView，逻辑放 Python 服务。

### 方案 B

Buildozer / python-for-android

- 适合快速原型。
- 复用 Python 较多。
- Android 原生系统能力会更难接。

## 真正打包前需要补的东西

- Android Manifest
- WebView Activity
- SAF 文件访问
- 悬浮窗权限
- 本地服务启动
- APK 签名配置
- 图标和启动页

## 现在可以先做的事情

- 继续扩 `toolkit/core`
- 继续补 `mobile_ui`
- 开始写 `shell/` 的原生工程说明


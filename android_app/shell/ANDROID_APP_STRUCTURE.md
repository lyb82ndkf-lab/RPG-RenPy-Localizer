# Android Shell Structure

建议的 Android 壳结构：

```text
shell/
  app/
    src/main/
      AndroidManifest.xml
      java/
      assets/
      res/
  build.gradle
  settings.gradle
```

## 壳层职责

- 打开 WebView。
- 读取本地 `mobile_ui` 页面。
- 申请文件访问权限。
- 启动本地 Python 服务。
- 申请悬浮窗权限。
- 转发按钮、摇杆、滑条事件。
- 根据游戏类型决定是否调用 Winlator 或 WebView。


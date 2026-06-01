# Android Backend

这里将放 Android 版的本地 Python 服务。

最终职责：

- 调用 `toolkit/core`。
- 提供本地 HTTP API。
- 管理翻译任务、嵌入任务、数据读取任务。
- 避免移动端界面因长任务卡死。

计划接口：

```text
POST /api/project/load
GET  /api/project/current
GET  /api/translate/entries
POST /api/translate/start
GET  /api/translate/job/{id}
GET  /api/data/summary
GET  /api/maps
POST /api/runtime/command
```


# RPG RenPy Localizer Android

这是 RPGRenPyLocalizer 的 UniApp + Vue3 迁移工程。

## 结构

- `pages/`：游戏库、翻译、数据、地图、存档、设置页面。
- `components/`：页面组件，按功能拆分。
- `api/`：`uni.request` 接口封装。
- `store/`：Pinia 状态管理。
- `utils/`：常量、格式化、文件访问桥。

## 当前阶段

当前版本完成了前端结构迁移和页面拆分。Android SAF 目录选择、实时游戏运行桥、原生悬浮/覆盖控制会继续通过 `utils/file-access.ts` 和原生插件接入。

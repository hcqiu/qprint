# Qprint 文档目录

[中文](index.md) | [English](index.en.md)

中文文档使用原文件名，英文版本使用 `.en.md`，两版保持相同范围。本文档集对应 `0.1.0` 及 2026-09-20 图谱分级扩展。

## 阅读路径

首次使用从 README 开始；理解目标阅读 PRODUCT；参与开发先读 ARCHITECTURE 和 spec，再按模块深入。TODO 是后续工作，verification 是历史实测记录。

| 内容 | 中文 | English |
| --- | --- | --- |
| 安装、启动与基本使用 | [README](../README.md) | [README](../README.en.md) |
| 产品定义与边界 | [PRODUCT](../PRODUCT.md) | [PRODUCT](../PRODUCT.en.md) |
| 架构与技术决策 | [ARCHITECTURE](../ARCHITECTURE.md) | [ARCHITECTURE](../ARCHITECTURE.en.md) |
| 待办与完成条件 | [TODO](../TODO.md) | [TODO](../TODO.en.md) |
| 开发规格 | [spec](spec.md) | [spec](spec.en.md) |
| 验收记录 | [verification](verification.md) | [verification](verification.en.md) |

## 模块文档

| 模块 | 内容 | English |
| --- | --- | --- |
| [Blueprint](blueprint.md) | 节点结构、元数据、链接和编写示例 | [Blueprint](blueprint.en.md) |
| [工作区](workspace.md) | 文件布局、路径、索引、诊断和保存 | [Workspace](workspace.en.md) |
| [知识图谱](graph.md) | 项目识别、引用聚合、范围和下钻 | [Graphs](graph.en.md) |
| [TeX 渲染](tex-rendering.md) | 标签、章节、片段、渲染和回退 | [TeX rendering](tex-rendering.en.md) |
| [形式化代码](formal-code.md) | Lean / Agda / Coq 绑定与定位 | [Formal code](formal-code.en.md) |
| [服务与 API](server-api.md) | 路径约定、请求、响应、错误和任务 | [Server and API](server-api.en.md) |
| [前端](frontend.md) | 阅读编辑、状态、导航与图谱交互 | [Frontend](frontend.en.md) |
| [导入器](importers.md) | GitHub / arXiv、归档限制和发布流程 | [Importers](importers.en.md) |
| [开发与验证](development.md) | 环境、CLI、测试、资源和排障 | [Development](development.en.md) |

原始中文需求保留于 [功能需求](../Qprint功能需求.md) 和 [blueprint 分级指南](../blueprint分级指南.md)，不替换为实现说明。仓库操作遵循 [AGENTS.md](../AGENTS.md)。

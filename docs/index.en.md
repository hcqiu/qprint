# Qprint documentation

[中文](index.md) | [English](index.en.md)

Chinese documents use the base filename; English documents use `.en.md`. Both versions cover the same scope: `0.1.0` and the graph granularity extension dated 2026-09-20.

## Reading paths

Start with README to use the application and PRODUCT to understand its purpose. Contributors should read ARCHITECTURE and the specification before individual module documents. TODO describes future work; verification records historical checks.

| Topic | 中文 | English |
| --- | --- | --- |
| Installation, startup, and basic usage | [README](../README.md) | [README](../README.en.md) |
| Product definition and boundaries | [PRODUCT](../PRODUCT.md) | [PRODUCT](../PRODUCT.en.md) |
| Architecture and decisions | [ARCHITECTURE](../ARCHITECTURE.md) | [ARCHITECTURE](../ARCHITECTURE.en.md) |
| Backlog and acceptance conditions | [TODO](../TODO.md) | [TODO](../TODO.en.md) |
| Development specification | [spec](spec.md) | [spec](spec.en.md) |
| Acceptance history | [verification](verification.md) | [verification](verification.en.md) |

## Module documents

| Module | Coverage | 中文 |
| --- | --- | --- |
| [Blueprint](blueprint.en.md) | Node structure, metadata, links, authoring examples | [Blueprint](blueprint.md) |
| [Workspace](workspace.en.md) | File layout, paths, indexing, diagnostics, saves | [工作区](workspace.md) |
| [Graphs](graph.en.md) | Project detection, reference aggregation, scope, drill-down | [知识图谱](graph.md) |
| [TeX rendering](tex-rendering.en.md) | Anchors, sections, fragments, rendering, fallbacks | [TeX 渲染](tex-rendering.md) |
| [Formal code](formal-code.en.md) | Lean / Agda / Coq bindings and lookup | [形式化代码](formal-code.md) |
| [Server and API](server-api.en.md) | Path conventions, requests, responses, errors, jobs | [服务与 API](server-api.md) |
| [Frontend](frontend.en.md) | Reading/editing, state, navigation, graph interaction | [前端](frontend.md) |
| [Importers](importers.en.md) | GitHub / arXiv, archive limits, publication | [导入器](importers.md) |
| [Development](development.en.md) | Environment, CLI, tests, assets, troubleshooting | [开发与验证](development.md) |

The original Chinese [functional requirements](../Qprint功能需求.md) and [blueprint granularity guide](../blueprint分级指南.md) remain as source requirements. Repository operations follow [AGENTS.md](../AGENTS.md).

# 浏览器前端模块

[中文](frontend.md) | [English](frontend.en.md) · [文档目录](index.md)

入口：[index.html](../qprint/static/index.html)、[style.css](../qprint/static/style.css)、[app.js](../qprint/static/app.js)。图谱：[graph-view.js](../qprint/static/graph-view.js)、[graph.js](../qprint/static/graph.js)。前端使用原生 ES modules 和 SVG，没有 npm 构建步骤。

## 页面与操作

左侧展示 Blueprint 文件夹、文件、节点与搜索，不显示论文目录或分组标题；中间展示节点正文、TeX 或整份 Markdown 编辑器；右侧展示语言与声明切换及代码。侧栏可折叠，窄屏时代码移至正文下方。诊断、渲染警告及代码定位错误由界面分别呈现。

| 操作 | 行为 |
| --- | --- |
| `/` | 非输入状态下聚焦搜索；搜索节点标题、路径及正文 |
| Alt + 左/右方向键 | 前往同一论文的前/后绑定节点 |
| Ctrl/Cmd + S | 在 Markdown 编辑模式保存整份文件 |
| Ctrl/Cmd + C / 右键复制 | 在节点阅读或 TeX 正文中复制选区，同时附带当前节点上下文；选区原文保持不变 |
| 正文滚动触边后再次滚动 | 切换相邻节点；设等待与冷却，编辑模式不触发 |
| 图谱单击 / 空格 | 预览对象 |
| 图谱双击 / Enter | 打开节点或按当前层级下钻 |
| 图谱拖动 / 滚轮 | 拖动节点、平移画布或缩放 |

滚动吸附只处理正文滚动区，并保留按钮与键盘替代方式。URL 使用 `#node=<编码后的节点 ID>`，支持深链与浏览器前后退；路径和标题变化会影响旧链接。

## 状态与请求

`app.js` 维护工作区数据、当前详情、阅读节点、视图/模式、代码绑定选项、编辑文档、dirty 状态及滚动边界。节点请求有递增序号，后发请求优先，过时响应不覆盖新的节点选择。

读取 `/api/project` 时保存会话 token，后续写请求带 `x-qprint-token`。刷新后保留仍存在的节点，否则选择可用目标。Markdown 编辑保存携带获取原文时的 revision；409 冲突显示错误，由用户重新载入合并。

离开有未保存修改的节点会提示确认；关闭页面使用 `beforeunload` 提醒。没有自动保存、冲突自动合并或浏览器持久草稿。

## 复制上下文

`clipboard-context.js` 处理节点正文的原生 `copy` 事件。默认复制当前节点完整 TeX、直接依赖的名称和简介，以及信息不足时使用 Knowledge Navigator 的简短提示。`User question:` 位于最后，后面逐字保留浏览器选区文本，不还原公式、不改写空白。Markdown 编辑器、搜索框、代码区、图谱和未绑定节点的整篇论文视图保持原生复制行为。

后台在工作区加载、刷新、保存和导入后的 `reload()` 中预生成内存 Context Bundle；`/api/node` 的 `copy_context` 随详情加载到浏览器，不额外发请求。原生复制事件同步写入剪贴板，不运行 Navigator、发网络请求或等待异步操作。上下文随节点详情替换；缺少缓存时保留普通复制。

默认 Level 0 不递归展开依赖，不复制依赖 TeX：最多 20 个直接 `uses` 依赖，简介最多 600 字符，依赖 ID、标题与简介总计最多 8,000 字符。Markdown 和 TeX `uses` 合并去重；思想来源不作为证明依赖。省略数量、未解析引用及缺少 TeX 的情况明确标记。需要 Level 1 描述或 Level 2 完整源文时，通过现有 Knowledge Navigator 的 `resolve`、`open`、`source` 按需读取。

## 图谱职责分离

从阅读页切换到知识图谱时，自动切回节点颗粒度、定位当前阅读节点所属的项目与 Milestone，并清除类型、状态和邻域筛选。当前节点高亮、居中并显示单击预览；力导向布局运动时保持居中，手动拖动、缩放或选择节点后停止自动跟随。

`graph-view.js` 不操作 DOM，负责颗粒度、项目范围、焦点与成员高亮。`app.js` 把投影数据和筛选交给图谱，处理预览、下钻与阅读跳转。`graph.js` 负责力导向/分层布局、SVG 边和节点、标签命中区域、键盘及鼠标交互。

下钻高亮独立于当前阅读节点；范围始终可选全范围、当前项目和当前 Milestone，Milestone 范围显示文件选择器，类型筛选仅在节点级启用。缩放时标签保持最小显示字号并扩大命中区域；控制栏与画布分开布局。具体分级规则见[图谱模块](graph.md)。

## 渲染与验证边界

论文正文支持 AMS 数学环境、表格行列与边框、定理名称和编号，以及 `\Cref` / `\cref` 的同节点和跨节点跳转。长论文的引用索引保留计数器结构，避免因全文过大而把编号退化成标签名；含下划线的标签按字面读取。`comment` 环境不进入正文、标注或引用索引。简单的 `\def` 数学别名会转换为受控宏定义，矩阵中的空列间距及公式标签里的定宽盒子近似为网页布局。

除 BibTeX `thebibliography` 外，也支持 AMSRefs 的 `bibdiv` / `biblist` / `\bib` BBL。保留作者、标题、出版信息、公式和链接；有显式 `label` 时使用该标签，否则网页按 BBL 条目顺序编号，正文引用与参考文献页使用同一组编号。

Formal Blueprint 的 `\lean{...}` 是形式化绑定元数据，不显示在 LaTeX 阅读正文中；TeX 原文和代码绑定仍保留。`\source{...}` 以 `Source: ...` 显示文献来源键，有已解析的参考文献时沿用文献跳转；连续的 `\dcref{...}` 合并为从 1 开始的编号列表，显示具体章节、定理和页码，并保留参数中的文字样式和公式。这些命令不产生排版降级警告，也不受印刷版空宏定义影响。

正文中的 `\includegraphics` 支持工作区 `tex/` 内的 PDF、PNG、JPEG、WebP、GIF（首帧），按源文件所在目录及 `\graphicspath` 查找；PDF 默认显示第一页，可用 `page=N` 指定页码。`tikzpicture`、`tikzcd` 以及行间公式中的 XY-pic `\xymatrix`、AMSCD 交换图独立编译，图片、图注和标签保留在原位。交换图连同外层公式一起生成，保留箭头、标签和周围运算。图形统一转为 PNG，缓存于工作区 `.qprint/cache/tex-media/`；图形失败时仅该图显示可展开的原文与诊断。普通阅读只使用已缓存的 TeX 宏包，不自动联网。

Conda 环境包含 Tectonic，Python 依赖包含 Pillow 和 pypdfium2。已有环境可用 `conda env update -p .\.conda -f environment.yml` 更新。首次使用某篇论文的 TikZ 时，在 Qprint 根目录运行以下预热命令（会下载所需 TeX 宏包）：

```powershell
.\.conda\python.exe -m qprint.tex_media --workspace examples/demo --paper Topology/KPT25TwoStabilizations/main.tex
```

TikZ 使用受限的独立前导区，只导入所需的简单命令定义和 TikZ 库；任意文件操作、动态 TeX 定义及外部图片嵌套不受支持。常规编译限时 30 秒；修改图片或图形源码后刷新工作区会生成新缓存。`\uses`、`\bpnode` 和普通引用仍使用原有导航。

后端通过关闭原始 HTML 的 Markdown 渲染和受控 TeX 适配器生成正文，前端显示普通文本时转义。KaTeX 与 auto-render 使用本地资源及 `trust: false`。静态资源由同一服务提供，正常阅读不依赖 CDN。

纯状态回归使用 `node --test tests/graph_view.test.mjs`。浏览器验收目前记录在[验收记录](verification.md)，还不是自动端到端测试；覆盖布局、焦点和拖拽等行为仍需浏览器检查。当前界面主要为中文，双语文档不意味着应用已经国际化。

Qprint：数学知识图谱 + proof navigation IDE

https://github.com/PatrickMassot/leanblueprint 是非常直观且美观的formal math和informal math对照系统，而Qprint在继承其原理和审美的前提下，作如下改进：
1. 将blueprint和tex解耦，blueprint node单独保存在md文件中，格式与Karpathy wiki/Obsidian 兼容，便于使用强大的知识库/AI工具。
2. 知识图谱用Obsidian的视觉和交互，更加现代化
3. blueprint和形式化代码解耦，这样可以用agda和coq等其他代码来形式化一个节点。
我们的工程代码可在https://github.com/PatrickMassot/leanblueprint 的基础上修改，具体如下：

（给人类看的）数学文件结构例子（具体子文件树参照lean或agda标准库的分法）：
├── pdf/
├── tex/
|   ├── Topology
|   |   └── Lin20K3.tex
│   ├── Algebra
│   └── Analysis
├── blueprint/
|   ├── Topology
|   |   └── Lin20K3.md
│   ├── Algebra
│   └── Analysis
├── agda/
|   ├── Topology
|   |   └── Lin20K3.agda
│   ├── Algebra
│   └── Analysis
└── lean/
    ├── Topology
    |   └── Lin20K3.lean
    ├── Algebra
    └── Analysis
pdf: 论文pdf，文件名和tex一致
tex: 储存论文的tex文件，标题为lastname + 年份 + 论文关键字
     文件中用标签表达“这段 LaTeX 内容属于哪个 blueprint node”，（包括没有包裹在begin end环境中的定义、证明等内容，如果它们是后文使用到的或者是形式化代码中的type/term，那么它们应当成为blueprint节点）。可以考虑使用自定义的plastex插件。例如https://github.com/PatrickMassot/leanblueprint 中用\lean，但我们这里形式化代码可以为lean agda coq等等，故不应局限。我建议用\bpnode{}来标。除此之外tex文件不多加标签，例如https://github.com/PatrickMassot/leanblueprint 里面还给tex文件加\leanok之类的，我们都不加。

blueprint: 储存md文件，分为两种：
  1. 记录重要数学对象（一般在标准库中已形式化），例如Thom space, Steenrod square这些。一个md文档包含标准库中一个文件的所有blueprint节点；它的一级标题为标准库中的declaration。如果标准库中没有，直接为该对象的名字
  节点记录的信息有：
    uses: 依赖的节点链接，格式例如[[Algebra/Homology#term]]
    lean：lean代码的链接, 格式例如module.declaration
    agda：agda代码的链接
    它是定义、引理、定理、猜想还是其他;
    形式化是否完成；
    思想借鉴了哪些节点；
  节点可以绑定0个或多个形式化代码。如果在标准库github中有，这个代码可能可以不需要实际在项目lean/agda/coq文件夹中，而是等需要用的时候再从github下载。
  节点被引用的方式：文件名#标题名。和Obsidian兼容。
  2. 一个md文档包含一篇论文的所有blueprint节点。标题和论文tex标题相同。一级标题为blueprint节点（定义定理证明等）。节点记录的信息有：
    tex: tex文件中的\node标签
    uses: 依赖的节点链接，格式例如[[Algebra/Homology#term]]
    lean：lean代码的链接, 格式例如module.declaration
    agda：agda代码的链接
    它是定义、引理、定理、猜想还是其他;
    形式化是否完成；
    思想借鉴了哪些节点；
  节点可以绑定0个或多个形式化代码。
  被引用的方式：文件名#标题名。和Obsidian兼容。



技术架构：tex和code都绑定在blueprint node上。

ui：参考https://leanprover-community.github.io/sphere-eversion/blueprint/index.html，左侧为目录（可缩回），显示的是tex文件的文件树 + tex文件内部section/subsection的目录（也就是渲染成pdf后的导航），但右侧分为两栏，informal math（可在tex和plastex渲染出来的html DOM中切换）在左栏，formal code在右栏（可缩回）。我希望这个界面基本和https://thefundamentaltheor3m.github.io/Sphere-Packing-Lean/blueprint/ 一样，只是多了个formal code的对照


点击知识图谱图标会进入blueprint的知识图谱，且聚焦在当前节点上。知识图谱的交互采用两种备选：1. 采用开源的Obsidian，例如https://github.com/nodummd/nodum 或者 webobsidian, 要求做到和闭源的obsidian app知识图谱一样炫酷；2. 和https://github.com/PatrickMassot/leanblueprint 以及https://leanprover-community.github.io/sphere-eversion/blueprint/index.html 里的图外观一样。
图应该是 navigation mechanism。比如点击：
SteenrodSquare
应该能够：
鼠标点击一下展示该数学对象的描述，例如https://imperialcollegelondon.github.io/FLT/blueprint/dep_graph_chapter_2.html 的界面。
双击打开对应 blueprint node，左侧定位 TeX，右侧定位 形式化代码
吸附：informal math展示的内容从上一个blueprint node绑定的tex到下一个blueprint node绑定的tex，右侧只显示当前blueprint node绑定的code。当鼠标滚轮滑动时，拉到底后再向下拉动切换到下一个blueprint node。

自动化插件：
1. 一个形式化代码自动下载器，给定保存形式化代码的仓库例如https://github.com/CMU-HoTT/serre-finiteness， 自动把里面的代码下载下来并保存到指定的子文件夹例如agda/serre-finiteness。
2. 论文自动下载器，给定arxiv号或者arxiv地址，给定保存pdf和tex文件夹下的子文件夹路径，自动下载论文pdf和tex文件到指定路径。
<!-- 3. 一个解析器，用来把已有的lean blueprint解析成我们的格式。例如https://github.com/thefundamentaltheor3m/Sphere-Packing-Lean/tree/main/blueprint/src，它的形式化代码在github，latex用了plastex插件。解析器应该能在不借助ai的情况下将其转换成我们的格式 -->

未来目标：ai agent可以在该结构的提示下双向生成：从tex生成形式化代码（参考https://prove2.me/tour/mission-captain 的Harness），或者反过来。参考https://github.com/prove2me/prove2me_workspace/blob/main/SKILL.md 的skill。

参考：https://prove2.me/tour/mission-captain
https://github.com/PatrickMassot/leanblueprint
https://leanprover-community.github.io/sphere-eversion/blueprint/index.html
Add side-by-side layout: TeX content left, Lean declarations right https://github.com/PatrickMassot/leanblueprint/pull/90
https://github.com/nodummd/nodum


## Python environment

This project uses the project-local Conda prefix `.conda`. Run from the Qprint root without activation; see AGENTS.md for first-time setup.

For Python commands, use:

.\.conda\python.exe ...

For pip:

.\.conda\python.exe -m pip ...

For tests:

.\.conda\python.exe -m pytest


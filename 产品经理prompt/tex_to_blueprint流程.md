# 文件标注格式
## tex文件标注格式
每个blueprint node的开头标注
\bpnode{name-of-node}
\bpdesc{description-of-node}
可以有多个相同标注（例如用于theorem和证明分开的情况）。如果blueprint node含有唯一的
\begin{}
\end{}
块而且该块有良好的\label{}，建议name-of-node标注为该label。

每个对其他node的依赖标注为
\uses{thm:open_ample, lem:open_ample_immersion}
该标签不改变论文tex中原有的\ref。该标签可以标在：
1. 论文tex中原有的\ref后方
2. 论文tex中有的\cite，如果引用的文章节点已经在可用blueprint节点中
3. 没有显示写出\ref的项的引用（例如一些数学对象，论文中通常不会显式引用），如果该项为blueprint节点，也要标注\uses
建议标注在紧接着对其他blueprint node中的内容的引用的后方，这样渲染时会出现引用链接。

# tex to blueprint
严格依据blueprint分级指南。
## agent标注
对没有被begin/end块包裹的定义（如果被超过一个blueprint节点使用）、证明等内容，也要标注为节点；
对没有显示写出\ref的项的引用（例如一些数学对象，论文中通常不会显式引用），如果该项为blueprint节点，也要标注\uses。
## 自动生成blueprint
一个自动化脚本，对tex文件中每个subsection生成一个md文件，文件中的一级标题为该subsection下全部blueprint节点，且节点信息含有tex文件中标注的该节点内所有的bpdesc、uses。
## agent review
自动生成blueprint完成后，agent重新看一遍md文件和tex文件，做适当地调整，使得每个md文件都是论文里的一个的milestone。为该项目生成一个索引md文件，记录
- 该项目的论文标题、作者、年份、关键字
- 该项目内的blueprint索引，
- 该项目依赖的项目（如果已在blueprint文件夹中）。

## agent权限
agent可以查看和修改本项目的tex文件（包括论文引用文件）和blueprint md文件。agent可以查看blueprint分级指南。agent可以通过脚本检索blueprint文件夹下其他项目的md文件（用于引用/建立依赖）。

# 测试用例
初步测试 https://arxiv.org/abs/2003.03925
压力测试：https://arxiv.org/abs/2510.12394

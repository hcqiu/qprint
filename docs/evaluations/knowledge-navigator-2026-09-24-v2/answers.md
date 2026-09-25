# 状态接口重测：完整回答

每项回答来自全新 subagent，未由主代理修改。

## V2L1

**题面：** “complete”：这里的 universe 为什么要假设 complete？

这里假设 **complete 主要是为了直接使用 May 的一般理论，省去逐项核查额外条件**。它的意思是：\(U\) 包含每一种不可约 \(G\)-表示的无穷多个副本。

但它**不是本文论证必不可少的假设**。作者在脚注明确说明：本文考虑的 \(G\)-CW 复形，其迷向子群只可能是 \(G\)、\(S^1\) 或 \(\{e\}\)，所以所有论证在较小的不完备 universe
\[
U_0=\mathbb R^{\oplus\infty}\oplus
\widetilde{\mathbb R}^{\oplus\infty}\oplus
\mathbb H^{\oplus\infty}
\]
中仍然成立；这个 \(U_0\) 也更贴近实际的几何背景。

因此，这里的 complete 是一个方便调用已有定理的加强假设，并不是说上述三个表示还不足以处理本文的问题。[原文及脚注](../../../examples/demo/tex/Topology/Lin20K3/main.tex:147)

## V2L2

**题面：** “twisted spin structure”：这里的 η·BF(M) 公式也适用于 Pin(2) 等变情形吗？

不能直接套用到 \(\mathrm{Pin}(2)\) 等变情形。这里的公式明确针对**非等变**不变量：
\[
\mathrm{BF}^{\{e\}}(M\times S^1,\tilde{\mathfrak s}^{\tau})
=
\begin{cases}
\eta\cdot\mathrm{BF}^{\{e\}}(M,\mathfrak s),&\sigma(M)\equiv16\pmod{32},\\
0,&32\mid\sigma(M).
\end{cases}
\]
其中 \(\eta\) 也是非等变稳定同伦中的 Hopf 元。

紧接着的备注明确将推广到 \(\mathrm{BF}^{G}\)（\(G=\mathrm{Pin}(2)\)）及 \(\mathrm{BF}^{S^1}\) 列为有待证明的问题。因此，**本文没有给出相应的等变公式**，但这也不等于断言它必然不成立。[原文公式与备注](../../../examples/demo/tex/Topology/Lin20K3/main.tex:619)

按定义，非等变不变量是 \(\mathrm{BF}^{G}\) 忘掉群作用后的限制；上述等式只确定这个限制，不能据此直接确定等变不变量。[限制关系](../../../examples/demo/tex/Topology/Lin20K3/main.tex:576)

## V2L3

**题面：** “BFᴳ(N,s) · e_R̃”：为什么稳定化后多出的是这个 Euler class？

因为连通和公式把稳定化的贡献变成了一个独立因子，而
\[
\mathrm{BF}^{G}(S^{2}\times S^{2})=e_{\widetilde{\mathbb R}}.
\]
这个等式有两层原因。

首先，\(S^{2}\times S^{2}\) 的 \(\sigma=0\)、\(b^{+}=1\)，所以有限维 Seiberg–Witten 映射的源、靶相差恰好一个 \(\widetilde{\mathbb R}\)：
\[
S^{m\widetilde{\mathbb R}+n\mathbb H}
\longrightarrow
S^{(m+1)\widetilde{\mathbb R}+n\mathbb H}.
\]
这一个额外方向来自自对偶调和二形式空间 \(H^{+}\)。微分形式上的 \(S^{1}\) 作用平凡、\(j\) 作用为 \(-1\)，所以它是**符号表示 \(\widetilde{\mathbb R}\)**。[有限维构造](/./examples/demo/tex/Topology/Lin20K3/main.tex:472)

其次，维数差只说明不变量落在哪个群里；确定它就是 Euler class，还要看映射。在 \(S^{1}\)-固定点上，该映射是标准包含
\[
S^{m\widetilde{\mathbb R}}
\hookrightarrow S^{(m+1)\widetilde{\mathbb R}}.
\]
文中的例子指出，此处的等变同伦类由这个限制决定。因此它是
\[
e_{\widetilde{\mathbb R}}
=\bigl[S^{0}=\{0,\infty\}\hookrightarrow S^{\widetilde{\mathbb R}}\bigr]
\]
的悬挂。[固定点计算与例子](/./examples/demo/tex/Topology/Lin20K3/main.tex:527)

最后，连通和公式给出
\[
\mathrm{BF}^{G}\!\left((N,\mathfrak s)\#((S^{2}\times S^{2})\times S^{1})\right)
=\mathrm{BF}^{G}(N,\mathfrak s)\wedge\mathrm{BF}^{G}(S^{2}\times S^{2})
=\mathrm{BF}^{G}(N,\mathfrak s)\cdot e_{\widetilde{\mathbb R}}.
\]
这里的“乘”就是稳定等变映射的 smash product。[连通和公式](/./examples/demo/tex/Topology/Lin20K3/main.tex:666)

扭曲 spin 结构也给出同一个因子：沿底空间圆周旋转其中一个 \(S^{2}\)，所得丛自同构交换乘积与扭曲 spin 结构，故这两个 spin family 同构。[对应引理](/./examples/demo/tex/Topology/Lin20K3/main.tex:456)

## V2L4

**题面：** “not smoothly isotopic to the identity map even after a single stabilization”：为什么这里一定要用 Pin(2)，只用 S¹ 不行吗？

**因为一次稳定化就会把这里的 \(S^1\) 等变 Bauer–Furuta 不变量变成零；\(\mathrm{Pin}(2)\) 等变不变量却仍能非零。**“一定要用”指的是本文这条证明路线，并不是断言所有其他方法都不可能。

设 \(N\) 是 Dehn twist 的映射环面，\(G=\mathrm{Pin}(2)\)，记 \(\alpha=\mathrm{BF}^G(N)\)。稳定化公式给出
\[
\mathrm{BF}^G(\widetilde N)=\alpha\,e_{\widetilde{\mathbb R}},
\]
其中 \(e_{\widetilde{\mathbb R}}\) 由包含映射 \(S^0\hookrightarrow S^{\widetilde{\mathbb R}}\) 表示。[稳定化公式](../../../examples/demo/tex/Topology/Lin20K3/main.tex:683)

关键在于这条一维表示：\(S^1\) 作用平凡，而额外的 \(j\in G\) 作用为 \(-1\)。限制到 \(S^1\) 后，可以把包含映射中的 \(0\) 沿实轴移到基点 \(\infty\)，得到等变零伦，因此
\[
\operatorname{Res}^G_{S^1}(e_{\widetilde{\mathbb R}})=0,
\qquad
\mathrm{BF}^{S^1}(\widetilde N)=0.
\]
保留 \(j\) 时，这个移动不再等变：\(j\) 会把移动方向反过来。[表示的定义](../../../examples/demo/tex/Topology/Lin20K3/main.tex:139)

不过，“不能这样收缩”本身还不足以证明 \(\alpha e_{\widetilde{\mathbb R}}\ne0\)。论文的关键命题补上了这一点：
\[
t(\operatorname{Res}\alpha)=0,\quad
\alpha e_{\widetilde{\mathbb R}}=0
\ \Longrightarrow\
\operatorname{Res}^G_{S^1}\alpha=0.
\]
这里第一个条件由连通和公式满足；若第二个条件也成立，忘掉全部群作用后，**稳定化前**的普通不变量也必须为零，却与 Kronheimer–Mrowka 算出的 \(\eta^3\ne0\) 矛盾。[关键命题](../../../examples/demo/tex/Topology/Lin20K3/main.tex:740)、[主定理证明](../../../examples/demo/tex/Topology/Lin20K3/main.tex:786)

所以 \(S^1\) 在证明里仍然有用：它帮助分析稳定化前的类。真正需要 \(\mathrm{Pin}(2)\) 的地方，是**保住经过一次稳定化后仍然存在的障碍**。

## V2K1

**题面：** “local of level k”：这个 k 具体量的是什么？

这里的 \(k\) 量的是 **\(S^1\) 固定点部分的实维数差（子丛的余维）**：
\[
k=\operatorname{rank}_{\mathbb R}F_0-\operatorname{rank}_{\mathbb R}E_0.
\]

定义要求：把源和目标的 \(S^1\) 固定点部分分别通过纤维同伦等价识别为 \(E_0^+\)、\(F_0^+\) 后，\(f^{S^1}\) 对应于子丛包含 \(E_0^+\hookrightarrow F_0^+\)。商丛 \(F_0/E_0\) 的每条纤维是 \(\widetilde{\mathbb R}^{\,k}\)，其中剩余的 \(\mathbb Z_2=\mathrm{Pin}(2)/S^1\) 以变号作用。

所以，**level \(k\) 表示固定点方向增加了 \(k\) 个实维度**；例如 \(k=0\) 时，该包含就是同秩子丛的同构，因而固定点上的映射是纤维同伦等价。

见[原文定义](/./examples/demo/tex/Topology/KPT25TwoStabilizations/main.tex:1590)。

## V2K2

**题面：** “X^{#2n} # Z”：为什么复制了 2n 份 X，却不需要复制 2n 份 Z？

因为证明中**同一份 \(Z\) 可以依次用来消去各份 \(X\) 上的扭转**。

关键是稳定化映射
\[
[f]\longmapsto[f\#\mathrm{id}_Z]
\]
在映射类群上良定义，并且不依赖把 \(Z\) 接在哪个位置。这里用到了 \(X\) 单连通，以及 \(Z\) 是 \(S^2\times S^2,\mathbb{CP}^2,\overline{\mathbb{CP}}^2\) 的连通和：Ruberman 引理描述的接合处球面扭转歧义，可以由这些稳定化块消除。[证明中的关键步骤](../../../examples/demo/tex/Topology/KPT25TwoStabilizations/main.tex:8945)

具体来说，先把各边界扭转移到内部的 \(Y_i^-\) 上。把 \(Z\) 接到第一份 \(X\) 的内部，便可用假设 \(T_{X\# Z,Y,\phi}^{k}\sim\mathrm{id}\) 消去第一项；同伦固定该块边界，因此能延拓到整个流形。随后利用接合位置的独立性，把**同一份 \(Z\)** 看作接到第二份 \(X\) 上，再消去第二项，依次进行。

而 **\(2n\) 的偶数性用于另一件事**：把边界扭转移向内部时，会产生接合球面上的修正扭转；它们在 \(2n\) 孔球面上的乘积同伦于恒等。因此，这些修正可以整体消掉，并不要求每份 \(X\) 各配一份 \(Z\)。[偶数孔球面推论](../../../examples/demo/tex/Topology/KPT25TwoStabilizations/main.tex:8875)

## V2K3

**题面：** “There does not exist a local map f: ℜ → M⊗M⊗M⊗M of level 2.”：三份的结论怎么推出这里四份的结论？

关键是存在一个 **level 0 的局部映射 \(p:M\to\mathfrak R\)**，可以用它消去第四个张量因子，而不改变 level。原文定义
\[
p(x_0)=1,\qquad p(x_i)=p(y_i)=0\quad(i=\pm1,\ldots,\pm5).
\]

假设存在 level 2 的 \(HOST_PATH R\to M^{\otimes4}\)，则考虑复合
\[
\mathfrak R\xrightarrow{\,f\,}M^{\otimes4}
\xrightarrow{\,\mathrm{id}^{\otimes3}\otimes p\,}
M^{\otimes3}\otimes_{\mathfrak R}\mathfrak R
\cong M^{\otimes3}.
\]
第二个映射是 level 0 的局部映射：局部化后，\(p\) 是拟同构，张量上前三个因子的恒等映射仍保持这一性质。因此，按文中的 level 相加引理，复合映射的 level 为 \(2+0=2\)。这就与“三份时不存在 level 2 局部映射”的结论矛盾。

所以这里能从三份推出四份，依赖的是这个特定的 **level 0 投影**，不能仅凭张量因子数量直接推断。参见[原文证明](../../../examples/demo/tex/Topology/KPT25TwoStabilizations/main.tex:9272)。

## V2K4

**题面：** “at least three copies of M”：既然三份就能给出代数障碍，最后为什么用了四份？

因为要同时满足两个条件：**代数障碍至少需要三份，而论文的几何复制构造要求偶数份，所以取四份。**

代数上，已有 level \(1\) 的局部映射 \(\mathfrak R\to M\)，张量平方就给出 level \(2\) 的 \(\mathfrak R\to M^{\otimes2}\)，因此两份无法产生矛盾；三份则确实不存在这样的映射。[原文说明](../../../examples/demo/tex/Topology/KPT25TwoStabilizations/main.tex:9283)

偶数条件出现在几何证明中：把各份 \(X\) 的边界扭转移过连通和挖去的球时，会多出球面 Dehn twist \(T_{S_i}^{\alpha}\)，其中各份具有相同的 \(\alpha\in\mathbb Z_2\)。偶数孔球面的边界扭转乘积同痕于恒等，因此这些修正项能消去。这使复制引理在**保持稳定化次数不变**的情况下给出 \(2n\) 份对应的局部映射；三份不在该引理保证的范围内。[几何复制证明](../../../examples/demo/tex/Topology/KPT25TwoStabilizations/main.tex:8900)

最后，三份的障碍自动推出四份的障碍：若存在 level \(2\) 的
\[
\mathfrak R\longrightarrow M^{\otimes4},
\]
就与 level \(0\) 的投影 \(\mathrm{id}^{\otimes3}\otimes p\)（\(p:M\to\mathfrak R\)）复合，得到被三份引理禁止的 level \(2\) 映射 \(\mathfrak R\to M^{\otimes3}\)。所以四份是这套证明中满足两项要求的最小份数。[四份推论](../../../examples/demo/tex/Topology/KPT25TwoStabilizations/main.tex:9265)

## V2K2R

**题面：** “X^{#2n} # Z”：为什么复制了 2n 份 X，却不需要复制 2n 份 Z？

因为**同一份 \(Z\) 可以依次用来消去每一份 \(X\) 上的扭转**。

关键是证明中建立的稳定化映射
\[
[f]\longmapsto[f\#\mathrm{id}_Z]
\]
在相对边界的同痕类上良定义，并且**与把 \(Z\) 接在哪一份 \(X_i\) 上无关**。这依赖于 \(X\) 单连通、Ruberman 引理，以及题设中 \(Z\) 的特殊组成：穿孔的 \(S^2\times S^2,\mathbb{CP}^2,\overline{\mathbb{CP}}^2\) 的球面边界扭转可以向内部延拓，从而处理改变连接位置产生的球面扭转歧义。

具体地，先把所有边界扭转移到各 \(X_i\) 的内侧，记为 \(t_i\)。把唯一的 \(Z\) 接在 \(X_1\) 的内侧，假设便给出
\[
(t_1^k\cdots t_{2n}^k)\#\mathrm{id}_Z
\sim(t_2^k\cdots t_{2n}^k)\#\mathrm{id}_Z.
\]
再利用连接位置无关性，把同一个稳定化因子看作接在 \(X_2\) 上，消去 \(t_2^k\)，如此继续。所有同痕都固定整个外边界。

**\(2n\) 的偶数性用于另一处**：把边界扭转移到内侧时会出现连接球面上的修正扭转；偶数穿孔球面的结论保证它们的乘积同痕于恒等。因此，偶数份 \(X\) 负责消除这些修正，而一份 \(Z\) 就能依次完成稳定化消去。[原证明](../../../examples/demo/tex/Topology/KPT25TwoStabilizations/main.tex:8930)

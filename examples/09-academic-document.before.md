# 提案手法の評価

重要なのは、提案手法の汎化性能を確認することです。本稿では、この汎化性能について多角的に掘り下げていきます。

評価は3つのデータセットで行いました。一部の条件では性能が劣化する可能性は否定できません。また、既定の設定のままでも実運用に適用できないわけではありません。

有意水準5%で検定した結果、データセットBについては帰無仮説は否定できないことが分かりました。

損失関数 $\mathcal{L} = -\sum_{i} y_i \log \hat{y}_i$ を最小化します。

$$
F_1 = \frac{2PR}{P + R}
$$

\begin{align}
p(x) &= \frac{1}{Z} \exp(-E(x))
\end{align}

図1: 提案手法と既存手法の精度比較の結果の概要

> "We observe consistent improvements across most benchmarks." (Suzuki et al., 2020)

## 参考文献

1. Suzuki, Y. et al. A comprehensive study of deep learning. Nature 500, 100–110 (2020).
[2] 田中太郎, 山田花子, "深層強化学習手法自己回帰型事前学習済言語モデルの包括的評価、多角的分析、および、その応用可能性の検討", 人工知能学会論文誌, vol. 35, no. 2, 2020.
Author, Alice. 2020. "A Comprehensive Study of Learning." American Sociological Review 85(3):45-67.

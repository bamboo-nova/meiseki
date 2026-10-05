# テキストブック（explainer.tex / explainer.pdf）の書き方

## 1. 役割

テキストブックは、定義・数式・例題で細部を詰めるための 1 冊である。絵解きノートが直感を受け持つので、こちらは正確さと手順を受け持つ。資料 1 つにつき 1 冊で、挑戦済みの論点をセッションのたびに書き足す。

原稿は `.rikai/<資料名>.explainer.tex` に置き、次のセッションで書き足すために残す。PDF は同じ場所の `<資料名>.explainer.pdf` に作る。

## 2. 原稿の骨組み

初回は次の骨組みから始める。プリアンブルに書くのは `\usepackage{rikai-textbook}` だけで、他のパッケージを足さない。体裁を 1 か所に固定すると、コンパイルエラーの余地が減る。例外は §8 の 2 つ（日本語以外の言語の文言と、フォントの指定）だけである。

```latex
\documentclass[10pt]{article}
\usepackage{rikai-textbook}
\begin{document}
\rikaititle{report.md}{2026-10-04}
\tableofcontents

\section{2. キャッシュ方針}
% >>> topic-001
\topic{通常キャッシュの有効期限}{復習中}
（この論点の本文）
% <<< topic-001

\end{document}
```

- `\rikaititle` の第 1 引数は資料名、第 2 引数は最終更新日である。更新のたびに日付を書き換える。
- `\section` には、文書の題のすぐ下の階層の見出しを、番号も含めてそのまま書く（例 `\section{2. 受付}`）。見出しの番号は LaTeX に付けさせない。資料に出てくる順に並べる。
- 論点 1 つは、`% >>> topic-NNN` と `% <<< topic-NNN` のコメント行で挟む。書き足しと差し替えは、この範囲を単位に行う。論点 id はこのコメントにだけ書き、読者に見える本文には書かない。
- `\topic{題名}{状態}` の状態は `復習中` か `卒業` である（日本語以外の言語では §8 の訳語）。

## 3. 論点 1 つの書き方

次の順に書く。当てはまらない部品は省く。

| 順 | 部品 | 書くこと |
|---|---|---|
| 1 | 導入の 1〜2 文 | この論点が何を区別・判断するものか |
| 2 | `youten` 環境 | 定義と結論。数式があれば番号付きで置く |
| 3 | 記号の表 | 数式に出てくる記号の意味と単位（`tabular` と `booktabs`） |
| 4 | `reidai` 環境 | 例題。計算の過程を 1 行ずつ示す |
| 5 | `mayoi` 環境 | 迷いどころ。誤答経験のある論点にだけ書く |
| 6 | `genbun` 環境 | 根拠になる原文の引用。必要最小限にする |

数式のない論点は、2 に定義を書き、3 の代わりに比較表（取り違えやすい用語を並べた表）を置く。

```latex
% >>> topic-020
\topic{SLE と ALE の計算式}{復習中}
1 回あたりの損失額と、1 年あたりの損失額を分けて見積もる。
\begin{youten}
単一損失予測 SLE は、資産価値 AV に露出係数 EF を掛けた額である。年間損失予測 ALE は、SLE に年間発生率 ARO を掛けた額である。
\begin{equation}
  \mathrm{SLE} = \mathrm{AV} \times \mathrm{EF}, \qquad \mathrm{ALE} = \mathrm{SLE} \times \mathrm{ARO}
\end{equation}
\end{youten}

\begin{tabular}{lL{0.45}l}
\toprule
記号 & 意味 & 単位 \\
\midrule
AV & 資産価値 & 円 \\
EF & その脅威で失う割合 & 0〜1 \\
ARO & 1 年間に起きる回数 & 回/年 \\
\bottomrule
\end{tabular}

\begin{reidai}[サーバの火災（説明用）]
$\mathrm{AV}=1{,}000$ 万円、$\mathrm{EF}=0.6$、$\mathrm{ARO}=0.1$ のとき、
\begin{align}
  \mathrm{SLE} &= 1{,}000 \times 0.6 = 600 \text{ 万円} \\
  \mathrm{ALE} &= 600 \times 0.1 = 60 \text{ 万円/年}
\end{align}
\end{reidai}

\begin{genbun}
「SLE = AV x EF」「ALE = SLE x ARO」
\end{genbun}
% <<< topic-020
```

## 4. 書くときの規則

- 事実の根拠は原文に限る。原文にない定義・数値・固有名詞を足さない。
- 例題の数値・名前・場面は、原文に例があればそれを使う。原文にないもので例題を作るときは、例題の題に「（説明用）」と添える。
- 数式は `equation` か `align` で書き、番号を付ける。記号は `\mathrm{...}`、式の中の日本語は `\text{...}` で書く。
- `reidai` の題は `\begin{reidai}[題]` のように省略できる引数で渡す。番号は文書の頭から通しで自動で付く。
- 文が入る列は `L{幅}` で書く（幅は行幅に対する割合。例 `\begin{tabular}{lL{0.6}}`）。`l` は短い語だけの列に使う。
- 図は TikZ で描く。必須ではない。関係・順序・時系列を 1 枚で示せるときにだけ使い、ノードは 6 個以内に収める。読み込み済みのライブラリは `arrows.meta` と `positioning` である。
- 文字として出したい `_ & % # $ { } ~ ^ \` は、次の表のとおりエスケープする。

| 文字 | 書き方 |
|---|---|
| `\` | `\textbackslash{}` |
| `&` | `\&` |
| `%` | `\%` |
| `$` | `\$` |
| `#` | `\#` |
| `_` | `\_` |
| `{` | `\{` |
| `}` | `\}` |
| `~` | `\textasciitilde{}` |
| `^` | `\textasciicircum{}` |

資料名や論点の題名は、次のコマンドの出力をそのまま使う。

```bash
python3 "<SKILL_DIR>/scripts/build_textbook.py" --escape 'report_v2 & notes.md'
```

資料の題名などを引数に書くときは単一引用符で囲み、二重引用符に入れない。シェルが `$` やバッククォートを解釈するためである。題名に単一引用符が含まれるときなど、確実に渡すには `--escape -` と指定して標準入力から渡す（例 `printf '%s\n' '<題名>' | python3 "<SKILL_DIR>/scripts/build_textbook.py" --escape -`。末尾の改行 1 つは取り除かれる）。

`python3` がない環境ではコマンドを使えないので、上の表に従って手で書き換える。元の文字列を 1 文字ずつ見て置き換え、置き換えたあとの文字（`\textbackslash{}` の `\` や `{}` など）をもう一度置き換えない。

## 5. ビルド

```bash
python3 "<SKILL_DIR>/scripts/build_textbook.py" --input "<原稿>" --output "<PDF>"
```

| 終了コード | 意味 | 対応 |
|---|---|---|
| 0 | PDF ができた | パスをユーザーに伝える |
| 1 | コンパイルに失敗した（300 秒で終わらなかった場合を含む） | 標準エラーに出た行番号と内容を読み、原稿を直して再実行する。`\rikaifont` を指定したあとの `fontspec` のエラーは、フォントが入っていないことを示す（§8）。3 回続けて失敗したら、原稿を残して失敗を伝える |
| 3 | xelatex がない | 原稿を残す。原稿を今回初めて作ったなら、標準エラーに出た導入方法をユーザーに伝える。そうでなければ、PDF を省いたことを 1 行で伝える。自分ではインストールしない |

終了コードが 0 でも、標準エラーに「[build_textbook] 警告: 次の文字はフォントになく、PDF に出ていません」と出たら、その文字は PDF に出ていない。直し方は、欠けた文字の種類で分ける。

- 紛れ込んだ記号（例 ≤、①）なら、原稿でその文字をほかの書き方に置き換え（例 ≤ → `$\le$`、① → (1)）、もう一度ビルドする。
- テキストブックを書いている言語の文字（ハングル、簡体字など）なら、文字は書き換えない。§8 のとおり `\rikaifont` でその文字を持つフォントを指定し、もう一度ビルドする。
- 原文の引用（`genbun`）に出る別の言語の文字だけが欠けるなら、§8 の最後の段落に従う。

スクリプトの警告は「原稿でほかの書き方に置き換えて」と続くが、置き換えるのは 1 つ目の場合だけである。

失敗したとき、前回の PDF はそのまま残る。

`python3` がない環境では、このコマンドを実行できない。原稿を残し、PDF を省いたことを 1 行で伝える（終了コード 3 のときと同じ）。

## 6. 書き直す条件

原稿は study.md に合わせる。載せるのは、挑戦済みで、アンカーが有効な論点（状態が `復習中` か `卒業`）である。状態が `要再抽出` の論点は書かない。次の 4 つを行い、それ以外の論点の範囲は書き直さない。

1. 載っていない論点の範囲を新しく書く。今回初めて挑戦した論点のほか、前回のセッションが途中で切れて書けなかった論点や、古い形式から移行した論点もこれに当たる。
2. `\topic` の状態が study.md と違う論点は、状態を書き換える。
3. 誤答があるのに `mayoi` 環境がない論点、今回の誤答で迷いどころが変わった論点は、`mayoi` 環境を書き足す。
4. 状態が `要再抽出` になった論点の範囲（`% >>>` から `% <<<` まで）は取り除く。根拠の段落が原文から失われているためである。その節に論点が 1 つも残らなければ、`\section` の行も取り除く。

## 7. 確認

- [ ] プリアンブルが `\documentclass[10pt]{article}` と `\usepackage{rikai-textbook}` だけである。日本語以外の言語では、ほかに §8 の `\renewcommand` の行（`\usepackage` と `\begin{document}` の間）と、必要なら `\newcommand{\rikaifont}{…}`（`\usepackage` の前）だけがある。
- [ ] 原稿全体が 1 つの言語で書かれている（§8）。
- [ ] 挑戦済みで状態が `復習中` か `卒業` の論点すべてに、対応する `% >>>` と `% <<<` の組がある。`要再抽出` の論点の範囲はない。
- [ ] `\topic` の状態が study.md と一致している。
- [ ] `\section` に資料の見出しが番号ごと書かれ、資料の見出しの順に並んでいる。
- [ ] 読者に見える本文に `topic-NNN` が出ていない。
- [ ] 原文にない数値・名前・場面を使った例題の題に「（説明用）」と書いてある。
- [ ] 文が入る表の列が `L{幅}` で書かれている。
- [ ] ビルドが終了コード 0 で終わり、文字が欠けた警告が出ていない。または、省いた理由をユーザーに伝えた。引用の文字だけが欠けたときは、欠けた文字をユーザーに伝えた（§8）。

## 8. 言語

原稿は、ユーザーの言語（依頼に使った言語。ユーザーが言語を指定したらその言語。判断できなければ日本語）で書く。原文の引用（`genbun` 環境）は資料の言語のままにする。原稿がすでにあれば、その原稿の言語で書き続ける。ユーザーが別の言語を求めたときに限り、原稿全体をその言語で書き直す。

囲みの題や目次の見出しなど、体裁が出す固定の文言は日本語が既定である。日本語以外の言語では、`\usepackage{rikai-textbook}` と `\begin{document}` の間に、次の `\renewcommand` の行を置いて文言を差し替える。プリアンブルに置いてよいのは、この行と、下のフォントの指定だけである。英語なら次のとおりに書く。

```latex
\documentclass[10pt]{article}
\usepackage{rikai-textbook}
\renewcommand{\rikaiLabelPoint}{Key point}
\renewcommand{\rikaiLabelExample}{Example}
\renewcommand{\rikaiLabelPitfall}{Where it gets confusing}
\renewcommand{\rikaiLabelSource}{Source}
\renewcommand{\rikaiLabelToc}{Contents}
\renewcommand{\rikaiLabelBook}{Textbook}
\renewcommand{\rikaiLabelUpdated}{Last updated}
\renewcommand{\rikaiLabelStatus}{Status}
\renewcommand{\rikaiLabelStatusSep}{: }
\renewcommand{\rikaiLabelDisclaimer}{Facts are based on the source text. Some numbers, names and situations in the examples were added for explanation.}
\begin{document}
```

| マクロ | 日本語（既定） | 英語 | 出る場所 |
|---|---|---|---|
| `\rikaiLabelPoint` | 要点 | Key point | `youten` の題 |
| `\rikaiLabelExample` | 例題 | Example | `reidai` の題（番号の前） |
| `\rikaiLabelPitfall` | 迷いどころ | Where it gets confusing | `mayoi` の題 |
| `\rikaiLabelSource` | 原文 | Source | `genbun` の先頭 |
| `\rikaiLabelToc` | 目次 | Contents | 目次の見出し |
| `\rikaiLabelBook` | テキストブック | Textbook | 題の下 |
| `\rikaiLabelUpdated` | 最終更新 | Last updated | 題の下（日付の前） |
| `\rikaiLabelStatus` | 状態 | Status | 論点の題の下 |
| `\rikaiLabelStatusSep` | ： | `: `（コロンと空白） | 状態の文言と値の間 |
| `\rikaiLabelDisclaimer` | 事実の根拠は資料の原文です。例題の数値・名前・場面には、説明のために足したものがあります。 | Facts are based on the source text. Some numbers, names and situations in the examples were added for explanation. | 題の下の注記 |

ほかの文言も、その言語で書く。study.md の論点の題名が原稿の言語と違う言語で書かれていれば、`\topic` には訳して書く。study.md の値は書き換えない。`\topic` の状態は study.md の値（`復習中`、`卒業`）を訳して書く（英語なら `Reviewing`、`Mastered`）。`\rikaititle` の日付と、原文にない例題の題に添える「（説明用）」も、その言語で書く（英語なら `October 4, 2026`、`(for illustration)`）。

フォントは、日本語とラテン文字の言語（英語、フランス語、ポルトガル語など）なら既定のままでよい。ほかの文字を使う言語（ハングル、簡体字など）では、その文字を持つフォントを `\usepackage` の前に指定する。指定しないと、文字が PDF に出ず、ビルドが §5 の警告を出す。

```latex
\documentclass[10pt]{article}
\newcommand{\rikaifont}{Apple SD Gothic Neo}
\usepackage{rikai-textbook}
```

指定するのは、その環境に実際に入っているフォントである。名前を 1 つ決め打ちせず、次の候補から入っているものを選ぶ。

| 言語 | 候補 |
|---|---|
| 韓国語 | `Apple SD Gothic Neo`（macOS）、`Malgun Gothic`（Windows）、`Noto Sans CJK KR`（入っている環境） |
| 簡体字中国語 | `PingFang SC`（macOS）、`Microsoft YaHei`（Windows）、`Noto Sans CJK SC`（入っている環境） |

`fc-list` があれば、入っているフォントを確かめてから選ぶ（例 韓国語は `fc-list :lang=ko family`、簡体字は `fc-list :lang=zh-cn family`）。表示されたファミリー名を `\rikaifont` に書く。

`\rikaifont` を指定したビルドが `fontspec` のエラー（フォントが見つからない。`rikai-textbook.sty` の行として示されることがある）で失敗したら、そのフォントは入っていない。style ファイルは直さず、別の候補を選んで再実行する。この再実行も、§5 の「3 回続けて失敗したら、原稿を残して失敗を伝える」に数える。

その言語の文字を持つフォントが 1 つも入っていなければ、原稿を残して PDF を省き、その言語のフォントが要ることを 1 行で伝える（xelatex がないときと同じ）。フォントは自分では入れない。

フォントは、原文の引用の文字も持っている必要がある（例 韓国語のテキストブックが日本語の資料を引用するなら、かなと漢字）。固定の文言を訳さずに日本語のまま残すと、その文字も要る。1 つのフォントで両方をまかなえなければ、テキストブックの言語の文字が出るフォントを優先する。引用の文字が欠けた警告はそのまま受け入れ、欠けた文字をユーザーに伝える。

---
name: jp-pdf
description: 日本語Markdownを配色付きのオフラインPDFに変換するスキル。「PDF化して」「PDFにして」「PDFを生成」「markdownをPDF」「日本語PDF」等で発動。IPAゴシック＋pandoc/xelatex（Chrome・Google不使用）、SVG図の埋め込み、色付き見出し・コールアウト引用・縞模様テーブルに対応。
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash, Read, Write, Edit
---

# jp-pdf — 日本語Markdown → 配色付きオフラインPDF

Markdown を、日本語が綺麗に組まれた**配色付き PDF** に変換する。生成経路は
**pandoc → xelatex のみ**で、Chrome や外部サービスを使わない（外部通信ゼロ）。

`<SKILL_DIR>` はこの `SKILL.md` があるディレクトリの実パスに読み替える。

## いつ使うか

- 「この Markdown を PDF にして」「研究計画書を PDF 化して」等の依頼。
- 日本語ドキュメント（設計書・提案書・レポート）を配布用の体裁で出したいとき。

## 前提ツール（すべてローカル／オフライン）

| ツール | 用途 | 導入例 |
|---|---|---|
| pandoc | Markdown→LaTeX→PDF | `brew install pandoc` |
| xelatex (TeX Live) | 日本語対応PDFエンジン | MacTeX / TeX Live |
| rsvg-convert (librsvg) | SVG図→ベクターPDF | `brew install librsvg` |
| IPAexGothic フォント | 日本語本文 | `~/Library/Fonts/ipaexg.ttf` |
| ghostscript (gs) | プレビュー(PNG) | `brew install ghostscript` |

不足時は build スクリプトが名前を挙げて停止する。

## 基本の手順

1. 入力 Markdown を用意（既存ファイルでよい）。図が無ければこの1手で完了。
2. ビルドを実行：

   ```bash
   python3 "<SKILL_DIR>/scripts/build_pdf.py" \
     --input path/to/doc.md \
     --output path/to/doc.pdf \
     --title "ドキュメント表題" \
     --running-title "ヘッダに出す短い題" --doc-tag "研究計画書" \
     --toc --preview
   ```

3. `--preview` を付けると1ページ目を `doc_p1.png` に出す。`gs` で任意ページを
   PNG化して目視確認する：

   ```bash
   gs -dSAFER -dBATCH -dNOPAUSE -sDEVICE=png16m -r120 \
      -dFirstPage=1 -dLastPage=3 -sOutputFile=out-%02d.png doc.pdf
   ```

## 図（ASCII図 → SVG）を入れる場合

本文中の ASCII 図を、見やすい SVG 図に差し替えられる。原稿 `.md` には ASCII を
残したまま、PDF ビルド時だけ画像に差し替える方式（原稿はエディタで読めるまま）。

1. `<SKILL_DIR>/scripts/svglib.py` を import して作図スクリプトを書く。雛形は
   `<SKILL_DIR>/../../examples/gen_diagrams.py`（svglib を import して使う）。
   角丸ボックス `box()`・矢印 `arrow()`・ラベル `label()`・チップ `chip()` を組む。
2. 生成した SVG を `assets/` に置く。
3. 「どの ASCII フェンスをどの SVG に差し替えるか」を `figures.json` で対応づける
   （雛形は `examples/figures.example.json`）：

   ```json
   [
     {"sig": "フェンス内に必ず含まれる一意な文字列", "svg": "pipeline.svg", "caption": "図：…"}
   ]
   ```

4. ビルドに `--assets assets --figures figures.json` を渡す。該当フェンスは
   `![caption](assets/xxx.pdf)` に置換され、SVG は自動でベクターPDF化される。

## 設計上の要点（この手順で踏んだ落とし穴）

- **完全オフライン**：Chrome/HTML 経路は使わない。pandoc→xelatex がローカル完結する
  ため、テレメトリや外部リソースのフェッチが発生しない。
- **フォント**：IPAexGothic は単一ウェイトのため、太字は `AutoFakeBold` で擬似化する
  （build スクリプトが既定で付与）。
- **配色**：`<SKILL_DIR>/assets/style.tex` が担う。ティール系で、色付き見出し＋下線罫、
  `tcolorbox` によるコールアウト引用（`>` ブロック）、`rowcolors` の縞テーブル、
  `fancyhdr` のヘッダ/フッタ、タイトル上下の罫線。
- **SVGの枠はみ出し**：`textLength`（引き伸ばし指定）は rsvg-convert の **PDF出力で
  無視される**（PNGでは効くので見落としやすい）。`svglib` は代わりに**フォントサイズ
  を実寸で縮めて**収める（`fitfs`）。作図時はこの `box()/label()` を使えば安全。
- **字形置換**：IPAexGothic に無い `✕`・`≈` はビルド時のみ `×`・`≒` に置換する
  （既定。原稿は不変）。他に欠字警告が出たら `--glyph-subs "字=代替,…"` を足す。
- **ラベルとボックスの重なり防止**：自由配置の `label()` を、ボックスの縦範囲（y〜y+h）と
  横範囲が交差する座標に置かない。矢印に添える名前は矢印の**上**の短い語だけにし、
  説明文はボックス行の**下に専用の帯**（縦方向のゾーン）を確保して置く。ゾーン同士は
  16px 以上離す。長文ラベルは `maxw` を必ず指定して縮小させる。
- **検証（必須）**：ビルド前に SVG 自体を `rsvg-convert -o check.png` で PNG 化して目視し、
  文字と枠・矢印の重なりがあれば直してから組み込む。ビルド後も `gs` でページを PNG 化し、
  図が枠に収まっているか・記号が出ているかを目視する。重なりが残ったまま完成としない。

## build_pdf.py の主なオプション

`--input --output`（必須）／`--assets DIR`／`--figures JSON`／`--title`／
`--running-title`／`--doc-tag`／`--style style.tex`（既定は同梱）／`--font`（既定 IPAexGothic）／
`--fontsize`（既定 10pt）／`--margin`（既定 16mm）／`--img-width`（既定 88%）／
`--toc`／`--preview`／`--glyph-subs "a=b,c=d"`。

## デモ（同梱サンプル）

`examples/` に汎用サンプル一式が入っている。次で一巡を試せる。

```bash
python3 "<SKILL_DIR>/../../examples/gen_diagrams.py" "<SKILL_DIR>/../../examples/assets"
python3 "<SKILL_DIR>/scripts/build_pdf.py" \
  --input "<SKILL_DIR>/../../examples/sample.md" \
  --output sample.pdf \
  --assets "<SKILL_DIR>/../../examples/assets" \
  --figures "<SKILL_DIR>/../../examples/figures.example.json" \
  --title "月次レポート自動化の検討メモ" --toc --preview
```

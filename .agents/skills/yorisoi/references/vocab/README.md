# 語彙リストの出典とライセンス

`vocab-check.js`（語彙レベル判定）が読むデータ。

## 同梱ファイル

### jlpt-tanos.csv（level, expression, reading）

- 出典: [tanos.co.uk の JLPT 語彙リスト](http://www.tanos.co.uk/jlpt/)（Jonathan Waller 氏、**CC BY**）。
  [jamsinclair/open-anki-jlpt-decks](https://github.com/jamsinclair/open-anki-jlpt-decks) と
  [elzup/jlpt-word-list](https://github.com/elzup/jlpt-word-list)（MIT）を経由して取得し、
  level / expression / reading の3列に整形した。
- **注意: JLPT の公式語彙リストは 2010 年以降非公開。** このリストは非公式の推定であり、
  判定結果の「N○相当」はすべて**推定値**である。
- 同一語が複数レベルに載る場合は、最も易しいレベルを採用している。

### kokugoken-basic.csv（kana, kanji, rank）

- 出典: 国立国語研究所『日本語教育のための基本語彙調査』（1984）の
  [公開データ](https://mmsrv.ninjal.ac.jp/bvjsl84/)（**CC BY 4.0**）。
  五十音順表（2_nihongokyoiku01.xlsx）から見出し語を抽出・整形した。
- rank=2000 は「基本語二千」（より基本的な語）、rank=6000 は基本語彙六千の残り。
- 判定では rank=2000 を常に許容し、rank=6000 は目標レベルが N3 以上のときに許容する。
- 見出し語のかな表記をキーにするため、同音異義語は区別しない（許容側に倒れる）。

## 任意ファイル（同梱しない）

### jev.csv（level, expression, reading）

- 「日本語教育語彙表」（JEV、17,908語・6レベル）は**二次配布禁止**のため同梱しない。
- 利用者が [配布元](https://jhlee.sakura.ne.jp/JEV/) から自分で入手し、
  level（1〜6 = 初級前半〜上級後半）, expression, reading の3列 CSV に変換して
  このディレクトリに `jev.csv` として置くと、vocab-check.js が最優先で参照する。
- `jev.csv` は `.gitignore` 済み。リポジトリにコミットしないこと。

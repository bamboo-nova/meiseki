# ADR-0001: やさしい日本語化スキル meiseki:yorisoi を追加する

- ステータス: Accepted（v0.6.0 で実装済み）
- 日付: 2026-09-05
- 決定者: bamboo-nova

## コンテキスト

meiseki は「一読で理解できる日本語」への書き換えを担うが、想定読者は日本語ネイティブに限られていた。
一方、在留外国人や行政文書の受け手に向けた「やさしい日本語」には公的な外部規範がある。
「在留支援のためのやさしい日本語ガイドライン」（出入国在留管理庁・文化庁、2020年8月）である。
この規範の多く（二重否定の禁止、一文一義、表記規則など）は機械判定に載せられる。

2026-09-05 の競合調査で、次の空白を確認した。

- textlint エコシステムに、やさしい日本語のプリセットと語彙レベルの判定ルールは存在しない
- Claude Code / Codex のスキルにも、規範準拠の変換と機械判定を備えたものはない
- 商用で最も近い「伝えるウェブ」はクローズドな SaaS で、ローカルで完結する決定論的検証を提供しない
- 学術系ツール（やさにちチェッカー、jReadability 等）は Web フォームのみで機械連携できない
- ISO 24495（プレインランゲージ）系のスキルは英語・中国語のみで、日本語版は空白

meiseki には「検出と採点は textlint（決定論層）、リライトは LLM 層」という二層構成の資産がある。
対象読者を変えれば、この資産をそのまま再利用できる。

## 決定

meiseki プラグインに第2スキル meiseki:yorisoi を追加する。

### 配置と構成

スキル名は yorisoi（寄り添い）とする。書き換えの本質が「読者の語彙レベル（N5〜N1）に合わせる」ことにあり、在留支援の文脈で定着した「寄り添う支援」とも重なるため。

`.agents/skills/yorisoi/` に以下を新設する。plugin.json の skills はディレクトリ指定のため、manifest の編集は不要。

```
.agents/skills/yorisoi/
├── SKILL.md                          # LLM オーケストレーター本体
└── references/
    ├── patterns-yorisoi.md          # ガイドライン由来の書き換えカタログ
    ├── textlint-yorisoi.config.json # やさしい日本語用の textlint 設定
    ├── prh-yorisoi.yml              # 推測表現・曖昧表現・表記規則の検出辞書
    └── vocab/                        # CC BY の語彙リスト（CSV）
```

meiseki 本体の「SKILL.md 1本と references 一式」という組を、もう1組作る構造とする。

### 動作モード

1. 変換モード: ガイドライン準拠のやさしい日本語へ書き換える
2. 判定モード: 書き換えずに、違反と語彙レベル超過を行位置つきで報告し、スコアを出す

自動適用 hook には載せない。対象読者が限定される機能のため、オンデマンド専用とする。
ふりがなと分かち書きは今回のスコープに含めない。

### 決定論層

- 既存 textlint ルールを再利用する（sentence-length、no-double-negative-ja など）
- ガイドライン固有の規則は prh の正規表現で近似する。対象は推測表現（「おそらく」等）や曖昧表現（「など」「ごろ」の多用）、受身・使役の典型形、表記規則（元号・「〜」・24時間表示）
- 語彙レベルは新規スクリプト `scripts/yorisoi-vocab-check.js` で判定する。kuromojin（kuromoji.js）で形態素解析し、同梱の語彙リストと照合し、レベル超過語を行位置つきで出力する
- `scripts/meiseki-lint-core.sh` は環境変数 `MEISEKI_LINT_CONFIG` による設定差し替えで再利用する。あわせてハードコード4点（npx パッケージリスト・集計 jq・閾値・マスキング）を環境変数で分岐できるよう改修する

### 語彙レベルの基準

- 既定は N4 相当とし、引数で N5〜N1 に変更できる
- JLPT の公式語彙リストは2010年以降非公開である。同梱する tanos リスト由来の「N○相当」は、すべて推定値と明示する
- 「日本語教育語彙表」（JEV）は二次配布禁止のため同梱しない。ユーザーが自分で入手して配置する、任意のオプション入力として扱う

### スコア

- YLS（やさしさ負荷スコア）: ガイドライン違反の重みつき件数 ÷ 文数 × 100。RLS と同型の定義
- 参考値として jReadability の公開式も併記する。品詞率だけで決定論的に計算できる

### レベル超過語の扱い

言い換えを優先する。言い換えできない重要語は「余震＜＝後から来る地震＞」の形式で残して説明する（ガイドライン準拠）。

### examples のスキル別構成への再編

スキルが複数になるため、examples/ をスキル別のサブディレクトリに分ける。

```
examples/
├── meiseki/    # 既存の9ペアと README をここへ移動
├── yorisoi/   # 変換の before/after ペアと README を新設
└── rikai/      # v0.7.0 で追加（ADR-0002 を参照）
```

移動に伴う修正は次のとおり。

- `scripts/test-meiseki-check.sh` が参照する examples/ 直下のパス4か所を更新する
- `examples/README.md` に記載した再現コマンドのパスを更新する
- hook の除外判定は `*/examples/*` のパス一致のため、サブディレクトリ化しても変更不要

## ライセンス・出典

- tanos JLPT リスト: CC BY。帰属表示のうえ同梱し、推定値であることを明示する
- 国語研「日本語教育のための基本語彙調査」データ: CC BY 4.0。帰属表示のうえ同梱する
- ガイドライン: 出典を SKILL.md と README に明記する。PDF の再配布はしない
- kuromoji.js / kuromojin: Apache-2.0 / MIT。npx 経由で取得する（初回のみ数十秒）

## 結果

- バージョンは v0.6.0。plugin.json（Claude / Codex）、marketplace.json、package.json の4か所を同期する
- README（日英）に yorisoi の説明を追加する
- examples/ をスキル別構成に再編し、examples/yorisoi/ に before/after を追加する
- textlint のバージョンピンの重複が現状5か所からさらに増える。実装時に定義の一元化を検討する
- npx の初回実行は kuromoji.js の取得に時間がかかる。以後はキャッシュされる

## 却下した代替案

- sudachi の wasm 版: 164MB と大きく、2022年から更新が止まっているため
- Python 層の導入: 「npx だけで動く」という meiseki の採用理由を壊すため
- ふりがな・分かち書きの付与: yasashii.org 等の表記法はあるが、今回はスコープ外とした
- hook 搭載: 全 Markdown への自動適用は、読者が限定される機能の性質に合わないため
- glossary 生成機能: 素の LLM でも実現でき、差別化基準を満たさないため棄却済み

## 参考資料

- [在留支援のためのやさしい日本語ガイドライン](https://www.moj.go.jp/isa/support/portal/plainjapanese_guideline.html)
- [tanos JLPT 語彙リスト（CC BY・非公式推定）](http://www.tanos.co.uk/jlpt/)
- [国語研『日本語教育のための基本語彙調査』データ（CC BY 4.0）](https://mmsrv.ninjal.ac.jp/bvjsl84/)
- [日本語教育語彙表 JEV（二次配布禁止・任意入手）](https://jhlee.sakura.ne.jp/JEV/)
- [jReadability](https://jreadability.net/) / [第三者実装 joshdavham/jreadability（MIT）](https://github.com/joshdavham/jreadability)
- [textlint-ja](https://github.com/textlint-ja)

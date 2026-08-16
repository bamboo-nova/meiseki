# meiseki

**AIが書いた日本語ドキュメントから読解負荷の高い構文を削ぎ落とし、一読で理解できる本文に書き直す Agent Skill。**

`meiseki`（明晰）＝澄んで分かること。目的は **明晰さ（clarity）= 内容を知らない読者が一度読んで正しく理解できること** だけ。
文章の声・立場・個性は足さない。一般論を「自分は」という意見に書き換えて主体性を注入する `stop-ai-slop-jp` 系とは
**逆方向**で、声を足さず中立な明晰さに振る。

> 開発の背景・モチベーションは作者の解説記事
> [AIの日本語を「自然」ではなく「明晰」にする ― meiseki という明晰化プラグインを作った話](https://zenn.dev/bamboo_nova/articles/c782c9de31e24b)（Zenn）を参照。

## 何を直すか

日本語ネイティブでも読解負荷の高い**構文**を対象にする（難しい語彙ではなく構文が読みにくさの原因）。

- 二重否定（litotes）/ 否定・条件の入れ子
- 長い連体修飾 / 主語‐述語の距離 / 一文への詰め込み
- 「の」の連鎖 / 過剰な名詞化・漢語
- 冗長・空虚な表現（「することができます」など）
- 太字＋コロンの箇条書き乱用などの過剰な体裁
- 一文に埋もれた 3 項目以上の同格列挙（箇条書きに開く）
- LLM 定型句（「重要なのは〜」「掘り下げる」「多角的」「〜に他ならない」など。同梱の prh 辞書で機械検出）
- 段落レベルの冗長（同じ主張の言い換え反復・描写直後の再要約・並列事実の分散）

**対象**：技術記事・README・設計書・社内ドキュメント・ブログの説明文。
**対象外**：コード本体・SNS の短文・小説や詩などの創作・法務／医療／論文の厳密文。

## アーキテクチャ（二層構成）

```
入力: 日本語ドキュメント（原稿）
        │
        ▼
[meiseki スキル / LLM オーケストレーター]
        │
        ├──▶ textlint（npx 実行・決定論層）
        │       二重否定・一文長・読点過多・連続漢字・冗長、
        │       LLM 定型句（prh 同梱辞書）などを
        │       行/列つきの機械可読(JSON)で検出 → 読解負荷スコア(before)
        │
        └──▶ パターンカタログ A–H（LLM 判断層）
                textlint では取れない構文を担当：
                長い連体修飾・「の」連鎖・名詞化・列挙の箇条書き化(F)・
                定型句の文脈判断(G)・段落レベルの反復の削除(H)
        │
        ▼
   リライト → textlint 再実行で before→after を検算
        │
        ▼
出力: 明晰化した本文のみ（＋任意で読解負荷スコア）
```

- **検出と採点は textlint（決定論層）**、**リライトはスキル（LLM 層）**に分ける。
- textlint で取れない構文（連体修飾・「の」連鎖・一般の名詞化・列挙）を LLM が担う。
  **この「textlint で取れない部分」が、単なる textlint 設定と meiseki の差**になる。
- MCP サーバーは持たない。textlint は Node.js 同梱の `npx` で呼ぶ。

## ディレクトリ構成

```
meiseki/
├── .claude-plugin/          # Claude Code プラグイン
├── hooks/
│   └── hooks.json           # PostToolUse hook 定義（プラグイン利用時の自動適用）
├── scripts/
│   ├── meiseki-check.sh         # hook 本体：md 書き込みを textlint で検査
│   └── test-meiseki-check.sh    # hook と prh 補完辞書の自動テスト（npm run test:hook）
├── skills/
│   └── meiseki/
│       ├── SKILL.md         # LLM オーケストレーター本体
│       └── references/
│           ├── patterns.md             # 高負荷構文カタログ A–H
│           ├── prh-llm-phrases.yml     # LLM 定型句の検出辞書（カテゴリ G・検出専用）
│           └── textlint.config.json    # 読解負荷に効くルールだけに絞った textlint 設定
├── package.json             # 開発用の npm run lint だけを提供
└── README.md
```

## 必要環境

* Node.js がインストールされていること

## インストール

### Agent Skill として使う

Node.js がインストールされた環境で以下を実行。

```
npx skills add https://github.com/bamboo-nova/meiseki --skill meiseki
```

### Claude Code プラグインとして使う（任意）

`claude plugin install` は**マーケットプレイスに登録されたプラグイン名**を取る（パスは取らない）。
そのため `claude plugin install ./meiseki` や `claude plugin install .` は失敗する。正しくは、
まず同梱の `.claude-plugin/marketplace.json` をマーケットプレイスとして登録し、その名前で install する。

```bash
# 1. このプラグインのマーケットプレイス(.claude-plugin/marketplace.json)を登録
claude plugin marketplace add ./meiseki

# 2. 「プラグイン名@マーケットプレイス名」で install
claude plugin install meiseki@bamboo-nova-ja-tools
```

開発中にインストールせず一時的に読み込むだけなら、こちらが手軽：

```bash
claude --plugin-dir ./meiseki
```

> マニフェストの検証は `claude plugin validate ./meiseki` で行える。

## 使い方

対象の日本語をスキルに渡すだけ。発動例：

- 「この README を読みやすく直して」
- 「この説明文、AIっぽいので明晰化して」
- 「冗長な日本語を削って一読で分かるようにして」

標準ではリライト後の**本文のみ**が返る。`「どこを直したか教えて」`と指定すると変更点も添える。
`「スコアも出して」`と指定すると読解負荷スコア(before→after)を併記する。

## 自動適用 hook（プラグイン利用時）

プラグインとして有効化すると、**Claude が日本語 Markdown を Write / Edit するたびに自動で検査が走る**。
hook 自体は LLM を呼ばない。textlint（決定論層）だけを実行し、読解負荷が高いときに
Claude へ「meiseki スキルを適用してリライトせよ」とフィードバックする。
Claude は同一セッション内で meiseki を適用し、ファイルを書き直す。

```
Claude が report.md を Write / Edit
        │
        ▼
[PostToolUse hook] scripts/meiseki-check.sh
  ├─ 対象外（.md 以外 / 除外パス / 日本語なし）→ 何もしない
  ├─ textlint 実行 → 指摘なし・軽微 → 何もしない
  └─ 二重否定あり or 指摘 3 件以上
       → decision:"block" + 指摘要約を Claude にフィードバック
       → Claude が meiseki を適用して再 Write（textlint 通過まで）
```

- **発動条件**：`no-double-negative-ja`（カテゴリ A）が 1 件以上、または textlint 指摘が計 3 件以上。
  分離型・丁寧形の二重否定（prh 補完辞書で検出）は通常の prh 指摘として合計に数える。
  なお本家 SKILL.md §7 の受け入れ基準は「after < before」の**相対比較**であり絶対閾値を持たないため、
  この発動条件は hook 側の簡易基準である（`scripts/meiseki-check.sh` 冒頭を参照）。
- **テスト**：`npm run test:hook`（= `scripts/test-meiseki-check.sh`）で、補完辞書の検出網羅と
  hook の判定・除外・ループ防止を自動テストできる。
- **除外**：`CLAUDE.md` / `AGENTS.md` / `MEMORY.md` / `SKILL.md`、`.claude/` `plans/` `memory/`
  `node_modules/` `.git/` `scratchpad/` `/tmp` 配下、`examples/`・`references/` 配下、
  日本語を含まないファイル。
- **ループ防止**：同一セッション・同一ファイルへの block は最大 2 回。以降は警告のみ
  （prh 指摘は「削除確定ではない」というガードレールと整合させるため）。
- **フェイルオープン**：textlint が実行できない環境（オフライン等）では書き込みを妨げない。
- **無効化**：環境変数 `MEISEKI_HOOK_DISABLE=1`、またはプラグイン自体の無効化。
- **PDF について**：PDF は生成後の修正ができないため、生成元の Markdown 段階でこの hook が
  明晰化を担保する（pandoc 等での PDF 化は明晰化済みの md から行われる）。

> hook の追加・変更はセッション再起動（またはプラグインの再読み込み）後に反映される。
> npx の初回実行はパッケージ取得で数十秒かかることがある（以後はキャッシュされる）。
> Agent Skill としてのみ（`npx skills add`）導入した場合、hook は付かない。従来どおり
> 依頼したときだけスキルが発動する。

## `references/textlint.config.json` のルール意図（差別化の肝）

フルプリセットは表記ゆれ・感嘆符・カタカナ長音など**読解負荷と無関係なルール**まで効いて「整えすぎ」になる。
meiseki は**読解負荷に効くルールだけ**を残し、それ以外を `false` で外している。

| 有効化（true） | 役割 |
|---|---|
| `no-double-negative-ja` | 二重否定（最優先カテゴリ A） |
| `sentence-length` (max 90) | 一文長（B） |
| `max-ten` (max 3) | 読点過多（B） |
| `max-kanji-continuous-len` (max 6) | 連続漢字＝漢語の重さ（C） |
| `ja-no-redundant-expression` | 冗長表現「することができる」等（C/D） |
| `no-doubled-joshi` (min_interval 1) | 助詞の重複（B） |
| `no-doubled-conjunction` | 接続詞の重複（D） |
| `no-doubled-conjunctive-particle-ga` | 逆接「が」の連続＝詰め込みの合図（B） |
| `ja-no-weak-phrase` | 弱い表現（D。※立場を強める方向には使わない） |
| `prh`（同梱辞書 `prh-llm-phrases.yml`） | LLM 定型句（G）。**検出専用**。削るか残すかは LLM が文脈判断する。加えて `no-double-negative-ja` が拾えない分離型・丁寧形の二重否定（「〜ないとは言えません」等）を A1 補完セクションで検出する |

無効化（false）：`arabic-kanji-numbers`, `no-mix-dearu-desumasu`, `ja-no-mixed-period`,
`no-dropping-the-ra`, `no-exclamation-question-mark`, `no-nfd`。

> **プリセット追従の注意**：`textlint` パッケージや `textlint-rule-preset-ja-technical-writing` パッケージの固定バージョンを変えると、
> `textlint-rule-preset-ja-technical-writing` のルールキーやデフォルト値も変わりうる。
> 変更時はプリセットの README でルール一覧を確認し、上記キーが存在するか・キー名が一致するかを点検すること。
> 読解負荷と無関係な同梱ルールが増えていたら、同様に `false` で外す。

## 読解負荷スコア（RLS）

```
RLS = Σ(カテゴリ件数 × 重み) ÷ 本文の文数 × 100   （低いほど読みやすい）
```

| カテゴリ | textlint ルール | 重み |
|---|---|---|
| A 否定の入れ子（最優先） | `no-double-negative-ja` | 3 |
| B 距離・長さ | `sentence-length`, `max-ten`, `no-doubled-conjunctive-particle-ga` | 2 |
| C 漢語・名詞化 | `max-kanji-continuous-len`, `ja-no-redundant-expression` | 2 |
| D 冗長・空虚 | `ja-no-redundant-expression`, `no-doubled-conjunction`, `ja-no-weak-phrase` | 1 |
| E 体裁 | （LLM 判断） | 1 |
| F 構造化（列挙） | （LLM 判断） | 1 |
| G 定型句 | `prh`（同梱辞書） | 1 |
| H 段落冗長 | （LLM 判断） | 1 |

**受け入れ基準：after < before を必須、A（二重否定）は原則 0 件。** 意図的な litotes だけ例外。

## 受け入れ基準チェックリスト

- [ ] 出力は本文のみ（分析・見出し・講評が付いていない）
- [ ] 冒頭の一般論（「近年〜」）が削られている
- [ ] 「することができます」→「できます」になっている
- [ ] 「〜の〜の〜」の連鎖がほどけている
- [ ] 長い連体修飾が分割され、主語‐述語が近い
- [ ] **二重否定が論理を反転させずに畳まれている**（例「招かないとは言えません」→「負荷が増えることがある」。「増えない」は誤訳＝不合格）
- [ ] 敬体／常体が維持されている
- [ ] API 名・固有名詞・数値が変わっていない
- [ ] 元から平易な文を不要に作り替えていない
- [ ] **声・立場が注入されていない**（「自分は」等の意見や、言い切りの強調が足されていない）
- [ ] LLM 定型句（「重要なのは〜」「掘り下げる」等）が削られている（文脈で実質を持つ用法は残っている）
- [ ] 段落レベルの言い換え反復・再要約が削られている（主張・例・根拠・例外は消えていない）
- [ ] textlint 再実行で読解負荷スコアが before より下がっている（A は 0 件）

## 参考資料

カテゴリ G（LLM 定型句）・H（段落レベルの冗長）の設計は、
k16shikano 氏の [日本語技術文書の文章規範](https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d)
（japanese-tech-writing skill）の「LLM っぽい空句の禁止」「冗長の排除」「段落と論証の構成」を参考にした。

## 免責事項

- 本Agent Skillおよびプラグインは「現状有姿（AS IS）」で提供され、出力結果の正確性・完全性・特定目的への適合性について**いかなる保証もしません**。
- meiseki は文章を**書き換える**ツールである以上、明晰化の過程で原文の意味・ニュアンス・事実関係が変化する可能性があります。**出力は必ず利用者自身が確認・検証したうえで使用してください。** 最終的な内容の責任は利用者にあります。
- 法務・医療・契約・論文など、表現の厳密さが要求される文書は**対象外**です（「何を直すか」参照）。これらの用途で生じた結果について作者は責任を負いません。
- 本Agent Skillおよびプラグインの使用または使用不能から生じた直接・間接のいかなる損害についても、作者および権利者は責任を負いません（詳細は `LICENSE` を参照）。
- 本Agent Skillおよびプラグインは textlint 等の第三者 OSS に依存します。それら依存パッケージの動作・セキュリティについては各提供元の規約・ライセンスに従います。

## ライセンス

MIT

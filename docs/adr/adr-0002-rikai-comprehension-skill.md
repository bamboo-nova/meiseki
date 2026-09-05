# ADR-0002: 理解度対話スキル meiseki:rikai を追加する

- ステータス: Proposed
- 日付: 2026-09-05
- 決定者: bamboo-nova

## コンテキスト

meiseki はこれまで書き手側の明晰化を担ってきた。
読み手側には、資料を正しく理解できたかを確かめる仕組みがない。
Anthropic の learning-opportunities スキルは、コーディング作業の途中に学習演習を挟む。
この発想をドキュメント読解に応用する。

2026-09-05 の競合調査で、次の状況を確認した。

- 日本語の技術資料を対象に、読者の理解度を対話で確認するスキルは存在しない
- 英語圏には tutor-skills（Obsidian Vault 前提の重量級）と socrates-skill（問答形式・汎用）がある
- Anthropic 公式の doc-coauthoring は模擬読者によるドキュメント検証を持つ。ただし測るのは文書の品質であり、読者の理解度とは別物である
- 誤答を書き手に還流し、リライトへ接続する閉ループを持つツールはどこにもない

この閉ループが本スキルの差別化の核になる。

## 決定

meiseki プラグインに第3スキル meiseki:rikai を追加する。

### 配置と構成

```
.agents/skills/rikai/
├── SKILL.md                 # LLM オーケストレーター本体
└── references/
    ├── question-design.md   # 出題設計ガイド（主張・前提・例外から問いを作る）
    └── study-format.md      # study.md のスキーマ定義
```

### ワークフロー

1. 資料を読み、主張・前提・例外を抽出して出題計画を立てる
2. AskUserQuestion の選択式で出題する
3. 誤答時は「なぜそう考えたか」を自由記述で問い、ソクラテス式の対話で原文へ誘導する
4. 原文の該当箇所を引用して解説する
5. 誤答した論点を study.md に記録する

### 三回挑戦法

- 誤答した論点は復習キューに入る
- 次回以降、同じ論点から別角度の問題を再生成して出題する
- 通算3回正解した論点は卒業とする（ライトナー法の簡易版）
- 状態は study.md の frontmatter で管理し、セッションを跨いで継続する

### 状態ファイル study.md

対象資料の隣に `<資料名>.study.md` を生成する。

- frontmatter: 論点 id・原文アンカー・挑戦履歴・状態（復習中 / 卒業）を機械可読で持つ
- 本文: 人が読める学習ノート
- 還流レポート: 誤答が集中した段落を、原文位置つきで列挙するセクション

### 書き手への還流

還流レポートは「実際に誤読を誘発した段落」の一覧になる。
書き手はこれを入力として、meiseki:meiseki で該当段落をリライトする。
理解度の測定と明晰化が、一つの閉ループとしてつながる。

### 実装上の割り切り

- LLM 層だけで完結する。textlint 層は使わない
- 自動適用 hook には載せない
- `*.study.md` は `scripts/meiseki-check.sh` の除外リストに追加する。学習ノートが明晰化の block を誘発するのを防ぐため

## 結果

- バージョンは v0.7.0（yorisoi の v0.6.0 の後に実装する）
- README（日英）に rikai の説明を追加する
- examples/rikai/ に、題材となる資料と study.md のサンプルを追加する（スキル別構成は ADR-0001 で定義）
- `scripts/meiseki-check.sh` の除外リストに1行追加する

## 却下した代替案

- Q&A 型のみ: 「Claude にファイルを渡して質問する」と区別できず、差別化基準を満たさないため
- Obsidian Vault 方式: tutor-skills と正面から競合し、導入も重くなるため
- SM-2 の間隔反復: 三回挑戦法で目的を満たせるうえ、実装が過重になるため
- グローバル状態（~/.meiseki/）: チーム共有と書き手還流の動線が弱くなるため

## 参考資料

- [learning-opportunities（DrCatHicks）](https://github.com/DrCatHicks/learning-opportunities)
- [tutor-skills（bevibing）](https://github.com/bevibing/tutor-skills)
- [socrates-skill（bevibing）](https://github.com/bevibing/socrates-skill)
- [doc-coauthoring（anthropics/skills）— Stage 3 Reader Testing](https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring)
- [kanketsu-jp/quiz — AskUserQuestion ベース出題の日本語先行例](https://github.com/kanketsu-jp/quiz)

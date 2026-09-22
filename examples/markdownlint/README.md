# markdownlint 適用例（Before / After）

meiseki v0.7.0 の Markdown 構文検査（リグレッションガード）が何を検出するかを示す例。
`01-broken-syntax.before.md`（同梱設定で有効化した全13ルールに違反する原稿）と
`01-broken-syntax.after.md`（違反 0 件に修正した版）の対で置いてある。
設定は `.agents/skills/meiseki/references/markdownlint.config.jsonc` を参照。

## before で発火するルール（実測）

| ルール | 検出内容 | before の行 |
|---|---|---|
| MD001 | 見出しレベルの飛び（h1 → h3） | 3 |
| MD018 | 見出し `#` の後にスペースがない | 5 |
| MD019 | 見出し `#` の後にスペースが複数ある | 7 |
| MD022 | 見出しの前後に空行がない | 10 |
| MD032 | リストの前後に空行がない | 12, 13, 35 |
| MD004 | リスト記号の混在（`-` と `*`） | 13 |
| MD005 | 同一階層のリストでインデント不一致 | 17 |
| MD009 | 行末の半角スペース（1つ。改行強制の2つは許容） | 19 |
| MD010 | 本文中のハードタブ | 21 |
| MD011 | リンク記法の逆転 `(text)[url]` | 23 |
| MD042 | 空リンク `[text]()` | 25 |
| MD031 | コードフェンスの前後に空行がない | 28 |
| MD047 | ファイル末尾に改行がない | 37 |

before の Go コードブロック内にはハードタブがあるが、**検出されない**（`MD010: code_blocks: false`）。
Go のようにタブが正であるコードへの誤爆を避ける較正で、meiseki が「コードは原文のまま」
（SKILL.md §3）としていることとも整合する。同じ理由で MD013（行長。1行=1段落の散文と衝突）と
MD041（先頭 h1。「本文だけ返す」仕様の文書断片と衝突）は無効にしてある。

> 再現方法：プラグインルートで次のように実行する。違反があると終了コード 1 で
> `file:line[:column] error MD###/alias 説明` の形式で出力される。
>
> ```bash
> npm run lint:md -- examples/markdownlint/01-broken-syntax.before.md   # 13 ルールが発火
> npm run lint:md -- examples/markdownlint/01-broken-syntax.after.md   # 違反 0 件
> ```

なお `examples/` 配下は自動適用 hook の除外対象なので、この before のように
わざと壊した Markdown を置いても block されない。

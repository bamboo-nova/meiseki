# 意味の検算の適用例（Before / After）

meiseki v0.11.0 の「意味の検算」が何を見つけ、何を見つけないかを示す例です。リライトの前（`*.before.md`）と後（`*.after.md`）の組で置いてあります。検算の仕組みは、ルートの README の「意味の検算」の節を参照してください。

## 意味を変えた書き換え（検出されるべきもの）

どれも一読では自然な書き換えに見えますが、意味が変わっています。

| 例 | 前 | 後 | 検出（実測） |
|---|---|---|---|
| `01-negation-flip` | 省略した場合に、影響がないとは言えません | 省略しても、影響しません | 否定の数が奇数だけ変わった（2 → 1）、条件「場合」が消えた |
| `02-number-change` | タイムアウトは 30 秒 | 60 秒 | 数値「30秒」が消え、「60秒」が現れた |
| `03-condition-drop` | ただし、管理者権限を持つユーザーに限ります | （削除） | 例外「ただし」・限定「に限り」が消えた |
| `04-hedge-strengthen` | 遅くなることがあります | 遅くなります | 可能性の印「ことがある」が消えた（言い切りへの変化） |
| `05-identifier-change` | `fetchUser` 関数 | `getUser` 関数 | 識別子が入れ替わった |
| `06-inline-code-change` | `` `config.yaml` `` | `` `config.yml` `` | インラインコードの中身が変わった |
| `07-scope-widen` | 一部の環境では、動作しないことがあります | 動作しないことがあります | 部分の印「一部」が消えた（範囲の拡大） |

`01` は、二重否定を畳むときに論理が反転する典型例です。「影響がないとは言えない」は「影響しうる」の意味なので、「影響しない」は逆の意味になります。

## 意味を保った書き換え（何も出ないべきもの）

| 例 | 内容 | 検出（実測） |
|---|---|---|
| `08-split-legit` | 長い一文を、2 つの段落に分けて整理した | 恐れあり 0 件 |
| `../meiseki/` の 9 組 | 明晰化の適用例 | 恐れあり 0 件（`01-retry` は二重否定の畳み込みとして「情報」を 1 件出す） |

## 原文に戻す例

`09-revert` は 2 段落の文書です。1 段落目は正しく書き換えてあり、2 段落目は `01` と同じ論理の反転を含みます。`--revert-risky` を付けると、2 段落目だけが原文に戻り、1 段落目の書き換えは残ります。戻した結果が `09-revert.expected.md` です。

## 試し方

プラグインのルートで実行します。依存パッケージは要らず、ネットワークにも接続しません。

```bash
# 1 組を検算する（恐れありが出ると終了コード 1）
npm run check:meaning -- --before examples/meaning/01-negation-flip.before.md --after examples/meaning/01-negation-flip.after.md

# 意味を保った書き換えでは何も出ない（終了コード 0）
npm run check:meaning -- --before examples/meaning/08-split-legit.before.md --after examples/meaning/08-split-legit.after.md

# 恐れありの段落だけを原文に戻す
npm run check:meaning -- --before examples/meaning/09-revert.before.md --after examples/meaning/09-revert.after.md --revert-risky --out /tmp/final.md
diff /tmp/final.md examples/meaning/09-revert.expected.md   # 差分なし

# ここにある例と examples/meiseki の 9 組をまとめて確かめる
npm run test:meaning
```

`01-negation-flip` の出力は次のとおりです。

```text
意味の検算: 恐れあり 2 件 / 情報 0 件
[F1] 恐れあり NEG 前 L1 / 後 L1: 否定の数が奇数だけ変わった(前 2 → 後 1)。論理が反転していないかを確かめる
      前の印: ない、ません
      後の印: ません
[F2] 恐れあり C 前 L1 / 後 L1: 条件の印が減った(前 1 → 後 0)
      前の印: 場合
      後の印: (なし)
判定していないもの: 意味が保たれたか(この検査は印の数を比べるだけで、何も出ないことは合格を意味しない)
```

## この検算で分からないこと

印の数を比べるだけなので、印を変えずに意味だけが変わった書き換えは見逃します。たとえば「A は B より速い」を「B は A より速い」にしても、何も出ません。何も出ないことは合格を意味しないので、スキルはこのあとも LLM の自己点検を続けます。

なお `examples/` 配下は自動適用フックの対象外なので、ここに意味を変えた文章を置いても書き換えられません。

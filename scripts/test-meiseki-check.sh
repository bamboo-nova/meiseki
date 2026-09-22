#!/usr/bin/env bash
# meiseki のテスト
#   Part 1: prh 補完辞書 — no-double-negative-ja が拾えない二重否定
#           (分離型・丁寧形)を prh が検出するか。誤検知・二重計上がないか。
#   Part 2: hook (scripts/meiseki-check.sh) — block 判定・除外・マスキング・
#           opt-out・ループ防止(内容ハッシュ・セッション横断)。
# 実行: npm run test:hook  (または bash scripts/test-meiseki-check.sh)
set -u
cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)

PASS=0; FAIL=0
ok() { PASS=$((PASS + 1)); echo "  ok  - $1"; }
ng() { FAIL=$((FAIL + 1)); echo "  NG  - $1"; }
assert_eq() { # desc expected actual
  if [ "$2" = "$3" ]; then ok "$1"; else ng "$1 (expected=[$2] actual=[$3])"; fi
}

TESTDIR=$(mktemp -d "$ROOT/.hooktest.XXXXXX")
SESSION="hooktest$$"
STATE="${TMPDIR:-/tmp}/meiseki-hook-state-test$$.tsv"
cleanup() { rm -rf "$TESTDIR"; rm -f "$STATE"; }
trap cleanup EXIT

lint() {
  npx --min-release-age=7 --yes \
    --package textlint@14.8.4 \
    --package textlint-rule-preset-ja-technical-writing@10.0.2 \
    --package textlint-rule-preset-ai-writing@1.1.0 \
    --package textlint-rule-prh@6.1.0 \
    textlint -c .agents/skills/meiseki/references/textlint.config.json -f json "$1" 2>/dev/null
}

hook() { # file [session]
  printf '{"session_id":"%s","tool_name":"Write","tool_input":{"file_path":"%s"}}' "${2:-$SESSION}" "$1" \
    | MEISEKI_HOOK_STATE="$STATE" ./scripts/meiseki-check.sh
}

echo "Part 1: prh 補完辞書(分離型・丁寧形の二重否定)"

# no-double-negative-ja が拾えないと実測で確認済みの形。1 行 1 形。
cat > "$TESTDIR/dn.md" <<'EOF'
問題を招かないとは言えない。
負荷の増大を招かないとは言えません。
この案は悪くなくはない。
バグの可能性は否定できません。
そのことを彼が知らないわけがない。
対応できないわけではありません。
失敗しないとは限りません。
対応できないこともありません。
読めなくもありません。
EOF
LINES=$(wc -l < "$TESTDIR/dn.md" | tr -d ' ')
HITS=$(lint "$TESTDIR/dn.md" | jq '[.[].messages[] | select(.ruleId == "prh") | .line] | unique | length')
assert_eq "未検出だった ${LINES} 形すべてを prh が検出する" "$LINES" "$HITS"

# 本家が拾う形(なくもない)は prh と二重計上しない
printf '読めなくもない。\n' > "$TESTDIR/native.md"
PRH=$(lint "$TESTDIR/native.md" | jq '[.[].messages[] | select(.ruleId == "prh")] | length')
CORE=$(lint "$TESTDIR/native.md" | jq '[.[].messages[] | select(.ruleId | endswith("no-double-negative-ja"))] | length')
assert_eq "「なくもない」を prh は検出しない(二重計上防止)" "0" "$PRH"
assert_eq "「なくもない」は本家ルールが検出する" "1" "$CORE"

# 統計の術語「(帰無)仮説は否定できない」は検出しない(意味を畳めないため)
printf '帰無仮説は否定できない。\n' > "$TESTDIR/stats.md"
STATS=$(lint "$TESTDIR/stats.md" | jq '[.[].messages[] | select(.ruleId == "prh")] | length')
assert_eq "「帰無仮説は否定できない」を prh は検出しない(統計文脈の除外)" "0" "$STATS"

# 単なる否定(二重でない)を誤検知しない
GOOD=$(lint "examples/meiseki/01-retry.after.md" | jq '[.[].messages[]] | length')
assert_eq "01-after(「再送するわけではありません」等)に誤検知なし" "0" "$GOOD"
E08A=$(lint "examples/meiseki/08-separated-double-negative.after.md" | jq '[.[].messages[]] | length')
assert_eq "08-after は指摘ゼロ" "0" "$E08A"
E08B=$(lint "examples/meiseki/08-separated-double-negative.before.md" | jq '[.[].messages[] | select(.ruleId == "prh")] | length')
assert_eq "08-before は prh 3 件" "3" "$E08B"

echo "Part 2: hook(meiseki-check.sh)"

# 分離型二重否定×3(prh のみ、本家 A は 0 件)→ 合計 3 件で block
cp examples/meiseki/08-separated-double-negative.before.md "$TESTDIR/sep-dn.md"
OUT=$(hook "$TESTDIR/sep-dn.md")
assert_eq "分離型二重否定×3 の md は block" "block" "$(printf '%s' "$OUT" | jq -r '.decision // "none"')"

printf 'この設定を省略すると、パフォーマンスに影響することがあります。\n' > "$TESTDIR/good.md"
assert_eq "良文 md は素通り(出力なし)" "" "$(hook "$TESTDIR/good.md")"
assert_eq "良文 md の 2 回目はリプレイで素通り" "" "$(hook "$TESTDIR/good.md")"

printf 'This is an English-only document.\n' > "$TESTDIR/english.md"
assert_eq "英語 md は素通り" "" "$(hook "$TESTDIR/english.md")"

cp "$TESTDIR/sep-dn.md" "$TESTDIR/CLAUDE.md"
assert_eq "除外パス(CLAUDE.md)は素通り" "" "$(hook "$TESTDIR/CLAUDE.md")"

assert_eq "MEISEKI_HOOK_DISABLE=1 で素通り" "" "$(MEISEKI_HOOK_DISABLE=1 hook "$TESTDIR/sep-dn.md")"

# ファイル単位 opt-out
{ printf -- '---\nmeiseki: skip\n---\n'; cat "$TESTDIR/sep-dn.md"; } > "$TESTDIR/optout-fm.md"
assert_eq "frontmatter meiseki: skip で素通り" "" "$(hook "$TESTDIR/optout-fm.md")"
{ cat "$TESTDIR/sep-dn.md"; printf '\n<!-- meiseki-disable -->\n'; } > "$TESTDIR/optout-marker.md"
assert_eq "<!-- meiseki-disable --> マーカーで素通り" "" "$(hook "$TESTDIR/optout-marker.md")"

# 学術文書: 参考文献・数式・図表キャプション・引用・脚注はマスクされ block しない
cat > "$TESTDIR/academic.md" <<'EOF'
# 提案手法の評価

本稿では、提案手法の評価結果を報告します。評価は3つのデータセットで行いました。

損失関数 $L = \sum_i (y_i - \hat{y}_i)^2$ を最小化します。

$$
L = \frac{1}{N} \sum_{i=1}^{N} (y_i - \hat{y}_i)^2
$$

\begin{align}
p(x) &= \frac{1}{Z} \exp(-E(x)) \\
Z &= \sum_x \exp(-E(x))
\end{align}

図1: 提案手法の全体構成の概要の模式図

表2: データセットごとの評価結果の比較の一覧

> 引用: 元論文の記述をそのまま示す。この結果の再現性は否定できないとは言えない。

[^1]: 脚注の定義。深層強化学習手法自己回帰型事前学習の詳細は付録を参照。

## 参考文献

1. Tanaka, T. & Suzuki, Y. 深層強化学習手法自己回帰型事前学習済言語モデルの包括的評価に関する研究、および多角的な分析、ならびに、その応用、展開、課題について. 人工知能学会論文誌 12, 34–56 (2020).
EOF
assert_eq "学術文書(参考文献・数式・キャプション・引用・脚注)は block しない" "" "$(hook "$TESTDIR/academic.md")"

# 参考文献フォーマット網羅: Nature / ASA / 和文が混在しても、セクション丸ごと
# マスクなのでフォーマットに依存しない。本文中の IEEE 行と脚注定義も対象外。
cat > "$TESTDIR/refs-formats.md" <<'EOF'
# 関連研究

先行研究の概要を述べます。詳細は各文献を参照してください。

[1] 山田太郎, 佐藤花子, 鈴木一郎, 高橋次郎, "深層強化学習手法自己回帰型モデルの包括的な評価手法の提案", 情報処理学会論文誌, vol. 61, no. 3, pp. 1-15, 2020.

[^2]: 対応できないわけではありませんが、この脚注は検査対象外です。

## References

1. Author, A. B. & Author, C. D. Comprehensive evaluation of deep learning. Nature Methods 12, 34–56 (2020).
Author, Alice. 2020. "A Comprehensive Study of Learning." American Sociological Review 85(3):45-67.
田中太郎・鈴木花子, 2020, 「深層強化学習手法自己回帰型事前学習の包括的検討、多角的評価、および、その課題、展望」『社会学評論』85(3): 45-67.
EOF
assert_eq "参考文献(Nature/ASA/和文/IEEE/脚注)は block しない" "" "$(hook "$TESTDIR/refs-formats.md")"

# mermaid: 日本語ラベル入りフローチャートはフェンスごとマスクされる
cat > "$TESTDIR/mermaid.md" <<'EOF'
# フロー

```mermaid
flowchart TD
  A[処理を開始しないとは言えない状態] --> B[極めて包括的な深層強化学習手法自己回帰型処理]
  B --> C[この設定を省略すると、パフォーマンスに、影響が、出ることが、あります]
```
EOF
assert_eq "日本語ラベル入り mermaid は block しない" "" "$(hook "$TESTDIR/mermaid.md")"

# prh G2(空虚な形容)は学術文書の本文でも直す対象としてカウントする
printf 'この手法は非常に優れています。この仕組みは不可欠です。この評価は極めて包括的です。\n' > "$TESTDIR/g2.md"
OUTG=$(hook "$TESTDIR/g2.md")
assert_eq "G2×4 の md は block する(曖昧表現は本文なら学術文書でも対象)" "block" "$(printf '%s' "$OUTG" | jq -r '.decision // "none"')"

# ループ防止: 同一セッション・同一ファイルの block は 2 回まで、3 回目は警告のみ
OUT2=$(hook "$TESTDIR/sep-dn.md")
assert_eq "同一ファイル 2 回目も block" "block" "$(printf '%s' "$OUT2" | jq -r '.decision // "none"')"
# 2 回目は内容ハッシュのリプレイ(再 lint なし)。同一 HASH の block 行が 2 本ある
REPLAY=$(awk -F'\t' -v f="$TESTDIR/sep-dn.md" '$2==f && $4=="block"{print $3}' "$STATE" | sort | uniq -c | awk '{print $1}')
assert_eq "2 回目はリプレイ(同一 HASH の block 行が 2 本)" "2" "$REPLAY"
OUT3=$(hook "$TESTDIR/sep-dn.md")
assert_eq "3 回目は block しない" "none" "$(printf '%s' "$OUT3" | jq -r '.decision // "none"')"
assert_eq "3 回目は additionalContext で警告する" "true" "$(printf '%s' "$OUT3" | jq -r '.hookSpecificOutput.additionalContext != null')"

# セッション横断: 別セッションでも block 済みの同一内容は advisory のみ
OUTX=$(hook "$TESTDIR/sep-dn.md" "othersession$$")
assert_eq "別セッションの同一内容は block しない" "none" "$(printf '%s' "$OUTX" | jq -r '.decision // "none"')"
assert_eq "別セッションの同一内容は additionalContext で警告する" "true" "$(printf '%s' "$OUTX" | jq -r '.hookSpecificOutput.additionalContext != null')"

echo ""
echo "Part 3: カテゴリ I(文字化け) — 警告のみで block しない"

# NFD 分離・ゼロ幅スペース・制御文字・半角カナ・U+FFFD の 5 種を含み、読解負荷は基準内の md
# (エディタでの再保存による正規化・除去を避けるため、対象文字はバイト列で書く)
printf '# 文字化けサンプル\n\nNFD分離: これは\xe3\x83\x9b\xe3\x82\x9aイントの説明です。\n\nゼロ幅スペース: ここに\xe2\x80\x8b見えない文字がある。\n\n制御文字: ベル文字\x07が混入している。\n\n置換文字: 変換に失敗した\xef\xbf\xbd文字がある。\n\n半角カナ: 警告 \xef\xbe\x83\xef\xbd\xba\xef\xbe\x9e\xef\xbd\xba\xef\xbe\x9e\xef\xbe\x86 にするのが自然です。\n' > "$TESTDIR/moji.md"
OUTM=$(hook "$TESTDIR/moji.md")
assert_eq "I 指摘 5 件でも block しない(RLS/閾値に数えない)" "none" "$(printf '%s' "$OUTM" | jq -r '.decision // "none"')"
assert_eq "I 指摘は additionalContext で警告する" "true" "$(printf '%s' "$OUTM" | jq -r '.hookSpecificOutput.additionalContext != null')"
assert_eq "警告に件数(5 件)が入る" "true" "$(printf '%s' "$OUTM" | jq -r '.hookSpecificOutput.additionalContext | contains("5 件")')"

# コア単体: I 指摘は integrity= に分離され、total= に混ざらない
OUTC=$(bash scripts/meiseki-lint-core.sh "$TESTDIR/moji.md")
assert_eq "コアの integrity=5" "5" "$(printf '%s\n' "$OUTC" | sed -n 's/^integrity=//p')"
assert_eq "コアの total=0(I を数えない)" "0" "$(printf '%s\n' "$OUTC" | sed -n 's/^total=//p')"

# 読解負荷 block と I 指摘の同居: block しつつ reason に I の注記が付く
printf '# t\n\nこの案は読めなくもない。この\xef\xbf\xbdは化けている。\n' > "$TESTDIR/moji-mix.md"
OUTMX=$(hook "$TESTDIR/moji-mix.md")
assert_eq "読解負荷があれば従来どおり block する" "block" "$(printf '%s' "$OUTMX" | jq -r '.decision // "none"')"
assert_eq "block の reason に文字化けの注記が付く" "true" "$(printf '%s' "$OUTMX" | jq -r '.reason | contains("文字化けの疑い")')"
assert_eq "I 指摘は block の件数に数えない(計 1 件)" "true" "$(printf '%s' "$OUTMX" | jq -r '.reason | contains("計 1 件")')"

# UTF-8 として不正(Shift_JIS): コアは exit 4、hook は警告のみ
printf '# タイトル\n\nこれは日本語の本文です。\n' | iconv -f UTF-8 -t SHIFT_JIS > "$TESTDIR/sjis.md"
bash scripts/meiseki-lint-core.sh "$TESTDIR/sjis.md" >/dev/null 2>&1
assert_eq "SJIS ファイルはコアが exit 4" "4" "$?"

# opt-out は UTF-8 妥当性検査より優先される(マーカーは ASCII なので SJIS でも読める)
{ cat "$TESTDIR/sjis.md"; printf '\n<!-- meiseki-disable -->\n'; } > "$TESTDIR/sjis-optout.md"
bash scripts/meiseki-lint-core.sh "$TESTDIR/sjis-optout.md" >/dev/null 2>&1
assert_eq "opt-out した SJIS ファイルは警告せず skip (exit 3)" "3" "$?"

# 回帰: 1KB 超の正当な UTF-8 を exit 4 と誤判定しない。macOS の iconv は
# 出力先が /dev/null だと約 1KB 超の出力で ENOTTY で失敗する(コアの回避策の検証)
i=0; : > "$TESTDIR/big-utf8.md"
printf '# 見出し\n\n' > "$TESTDIR/big-utf8.md"
while [ $i -lt 60 ]; do printf 'この文書は正当な文字コードで書かれた本文です。\n' >> "$TESTDIR/big-utf8.md"; i=$((i+1)); done
bash scripts/meiseki-lint-core.sh "$TESTDIR/big-utf8.md" >/dev/null 2>&1
RC_BIG=$?
assert_eq "1KB 超の正当な UTF-8 は exit 4 にならない" "false" "$([ "$RC_BIG" = "4" ] && echo true || echo false)"
OUTS=$(hook "$TESTDIR/sjis.md")
assert_eq "SJIS ファイルは block しない" "none" "$(printf '%s' "$OUTS" | jq -r '.decision // "none"')"
assert_eq "SJIS ファイルはエンコーディング警告を出す" "true" "$(printf '%s' "$OUTS" | jq -r '.hookSpecificOutput.additionalContext | contains("UTF-8 として読めません")')"

echo ""
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]

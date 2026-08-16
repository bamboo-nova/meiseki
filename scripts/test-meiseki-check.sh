#!/usr/bin/env bash
# meiseki のテスト
#   Part 1: prh 補完辞書 — no-double-negative-ja が拾えない二重否定
#           (分離型・丁寧形)を prh が検出するか。誤検知・二重計上がないか。
#   Part 2: hook (scripts/meiseki-check.sh) — block 判定・除外・ループ防止。
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
STATE="${TMPDIR:-/tmp}/meiseki-hook-${SESSION}.txt"
cleanup() { rm -rf "$TESTDIR"; rm -f "$STATE"; }
trap cleanup EXIT

lint() {
  npx --min-release-age=7 --yes \
    --package textlint@14.8.4 \
    --package textlint-rule-preset-ja-technical-writing@10.0.2 \
    --package textlint-rule-prh@6.1.0 \
    textlint -c skills/meiseki/references/textlint.config.json -f json "$1" 2>/dev/null
}

hook() { # file
  printf '{"session_id":"%s","tool_name":"Write","tool_input":{"file_path":"%s"}}' "$SESSION" "$1" \
    | ./scripts/meiseki-check.sh
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

# 単なる否定(二重でない)を誤検知しない
GOOD=$(lint "examples/01-retry.after.md" | jq '[.[].messages[]] | length')
assert_eq "01-after(「再送するわけではありません」等)に誤検知なし" "0" "$GOOD"
E08A=$(lint "examples/08-separated-double-negative.after.md" | jq '[.[].messages[]] | length')
assert_eq "08-after は指摘ゼロ" "0" "$E08A"
E08B=$(lint "examples/08-separated-double-negative.before.md" | jq '[.[].messages[] | select(.ruleId == "prh")] | length')
assert_eq "08-before は prh 3 件" "3" "$E08B"

echo "Part 2: hook(meiseki-check.sh)"

# 分離型二重否定×3(prh のみ、本家 A は 0 件)→ 合計 3 件で block
cp examples/08-separated-double-negative.before.md "$TESTDIR/sep-dn.md"
OUT=$(hook "$TESTDIR/sep-dn.md")
assert_eq "分離型二重否定×3 の md は block" "block" "$(printf '%s' "$OUT" | jq -r '.decision // "none"')"

printf 'この設定を省略すると、パフォーマンスに影響することがあります。\n' > "$TESTDIR/good.md"
assert_eq "良文 md は素通り(出力なし)" "" "$(hook "$TESTDIR/good.md")"

printf 'This is an English-only document.\n' > "$TESTDIR/english.md"
assert_eq "英語 md は素通り" "" "$(hook "$TESTDIR/english.md")"

cp "$TESTDIR/sep-dn.md" "$TESTDIR/CLAUDE.md"
assert_eq "除外パス(CLAUDE.md)は素通り" "" "$(hook "$TESTDIR/CLAUDE.md")"

assert_eq "MEISEKI_HOOK_DISABLE=1 で素通り" "" "$(MEISEKI_HOOK_DISABLE=1 hook "$TESTDIR/sep-dn.md")"

# ループ防止: 同一セッション・同一ファイルの block は 2 回まで、3 回目は警告のみ
OUT2=$(hook "$TESTDIR/sep-dn.md")
assert_eq "同一ファイル 2 回目も block" "block" "$(printf '%s' "$OUT2" | jq -r '.decision // "none"')"
OUT3=$(hook "$TESTDIR/sep-dn.md")
assert_eq "3 回目は block しない" "none" "$(printf '%s' "$OUT3" | jq -r '.decision // "none"')"
assert_eq "3 回目は additionalContext で警告する" "true" "$(printf '%s' "$OUT3" | jq -r '.hookSpecificOutput.additionalContext != null')"

echo ""
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]

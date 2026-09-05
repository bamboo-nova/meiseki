#!/usr/bin/env bash
# meiseki:yorisoi のテスト
#   Part 1: prh-yorisoi.yml — ガイドライン由来の検出(A1/YC/YD/YE/YG)が効くか。
#           やさしい日本語の良文に誤検知がないか。
#   Part 2: vocab-check.js — 語彙レベル超過の検出・許容・終了コード。
#   Part 3: examples/yorisoi — after は textlint 0 件かつ語彙超過 0。
# 実行: npm run test:yorisoi  (または bash scripts/test-yorisoi.sh)
# 注意: 初回は npx / npm のパッケージ取得で数十秒かかる。
set -u
cd "$(dirname "$0")/.." || exit 1

PASS=0; FAIL=0
ok() { PASS=$((PASS + 1)); echo "  ok  - $1"; }
ng() { FAIL=$((FAIL + 1)); echo "  NG  - $1"; }
assert_eq() { # desc expected actual
  if [ "$2" = "$3" ]; then ok "$1"; else ng "$1 (expected=[$2] actual=[$3])"; fi
}

TESTDIR=$(mktemp -d "$(pwd)/.yorisoitest.XXXXXX")
cleanup() { rm -rf "$TESTDIR"; }
trap cleanup EXIT

CONFIG=.agents/skills/yorisoi/references/textlint-yorisoi.config.json
lint() {
  npx --min-release-age=7 --yes \
    --package textlint@14.8.4 \
    --package textlint-rule-preset-ja-technical-writing@10.0.2 \
    --package textlint-rule-prh@6.1.0 \
    textlint -c "$CONFIG" -f json "$1" 2>/dev/null
}
vocab() { node scripts/yorisoi-vocab-check.js --level "${2:-N4}" --format json "$1"; }

echo "Part 1: prh-yorisoi.yml(ガイドライン由来の検出)"

# 1 行 1 違反。行数と prh 検出行数が一致すること
cat > "$TESTDIR/viol.md" <<'EOF'
申請できないわけではありません。
会場でマスクの着用が求められます。
作文を書かされます。
おそらく雨です。
中止になるおそれがあります。
書類等を持ってきてください。
市長がいらっしゃいます。
ご不明な点は市役所へお越しください。
締め切りは令和7年3月10日です。
受付は9時〜11時です。
開始は18時です。
期限は2025/2/28です。
EOF
LINES=$(wc -l < "$TESTDIR/viol.md" | tr -d ' ')
HITS=$(lint "$TESTDIR/viol.md" | jq '[.[].messages[] | select(.ruleId == "prh") | .line] | unique | length')
assert_eq "違反 ${LINES} 行すべてで prh が検出する" "$LINES" "$HITS"

# 文末統一(no-mix-dearu-desumasu)が有効
printf 'ゴミは月曜日に出してください。回収は市が行うものである。\n' > "$TESTDIR/mix.md"
MIX=$(lint "$TESTDIR/mix.md" | jq '[.[].messages[] | select(.ruleId | endswith("no-mix-dearu-desumasu"))] | length')
assert_eq "です・ます混在を検出する" "1" "$MIX"

# やさしい日本語の良文に誤検知がない(「かもしれません」は指摘しない)
cat > "$TESTDIR/good.md" <<'EOF'
ごみは、決められた日の朝8時までに出してください。

雨の日は、集める時間が遅れるかもしれません。
EOF
GOOD=$(lint "$TESTDIR/good.md" | jq '[.[].messages[]] | length')
assert_eq "良文(かもしれません含む)は指摘ゼロ" "0" "$GOOD"

echo "Part 2: vocab-check.js(語彙レベル判定)"

printf '迅速な対応をお願いします。\n' > "$TESTDIR/hard.md"
HAS=$(vocab "$TESTDIR/hard.md" | jq '[.over[].word] | index("迅速") != null')
RC=0; vocab "$TESTDIR/hard.md" >/dev/null || RC=$?
assert_eq "「迅速」を N4 目標で超過と判定する" "true" "$HAS"
assert_eq "超過ありの終了コードは 1" "1" "$RC"

RC=0; vocab "$TESTDIR/hard.md" N1 >/dev/null || RC=$?
assert_eq "同じ文でも N1 目標なら超過なし(終了コード 0)" "0" "$RC"

RC=0; vocab "$TESTDIR/good.md" >/dev/null || RC=$?
assert_eq "良文は超過なし(終了コード 0)" "0" "$RC"

# 基本語彙(国語研)による許容: JLPT 推定で上位でも基本語二千なら通す
printf '健康の結果を知らせます。\n' > "$TESTDIR/basic.md"
OVER=$(vocab "$TESTDIR/basic.md" | jq '.over | length')
assert_eq "基本語二千(健康・結果)は N4 目標でも超過にしない" "0" "$OVER"

# 固有名詞と定型表現の分解片は判定対象外
printf '田中さんはアメリカに行くかもしれません。\n' > "$TESTDIR/proper.md"
BOTH=$(vocab "$TESTDIR/proper.md" | jq '(.over + .unknown) | length')
assert_eq "固有名詞・「しれる」を報告しない" "0" "$BOTH"

# コードブロックと引用は判定対象外
cat > "$TESTDIR/masked.md" <<'EOF'
朝8時までに出してください。

```
迅速な対応の蓋然性を検証する。
```

> 迅速な対応をお願いします。
EOF
RC=0; vocab "$TESTDIR/masked.md" >/dev/null || RC=$?
assert_eq "コード・引用内の難語は判定しない(終了コード 0)" "0" "$RC"

echo "Part 3: examples/yorisoi(before は検出あり・after はゼロ)"

for name in 01-notice 02-notation 03-vocab; do
  B="examples/yorisoi/$name.before.md"
  A="examples/yorisoi/$name.after.md"
  BT=$(lint "$B" | jq '[.[].messages[]] | length')
  BO=$(vocab "$B" | jq '.over | length')
  AT=$(lint "$A" | jq '[.[].messages[]] | length')
  AO=$(vocab "$A" | jq '.over | length')
  if [ "$((BT + BO))" -gt 0 ]; then ok "$name.before に検出がある(textlint=$BT vocab=$BO)"; else ng "$name.before に検出がない"; fi
  assert_eq "$name.after は textlint 0 件" "0" "$AT"
  assert_eq "$name.after は語彙超過 0" "0" "$AO"
done

# lint-core のルールセット差し替え(環境変数)で yorisoi 構成が動く
RC=0
MEISEKI_LINT_CONFIG="$CONFIG" \
MEISEKI_LINT_PACKAGES="textlint@14.8.4 textlint-rule-preset-ja-technical-writing@10.0.2 textlint-rule-prh@6.1.0" \
bash scripts/meiseki-lint-core.sh "$TESTDIR/viol.md" >/dev/null || RC=$?
assert_eq "lint-core を yorisoi 構成で実行すると block(rc=1)" "1" "$RC"

echo ""
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]

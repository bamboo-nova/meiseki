#!/usr/bin/env bash
# meiseki-lint-core.sh <file.md>
#
# meiseki の決定論層(ホスト非依存コア)。
# 対象判定(日本語・opt-out) → 対象外領域のマスキング → textlint → 閾値判定を行う。
# Claude Code フック(meiseki-check.sh)・Codex フック(codex-hook.sh)・
# git pre-commit などのアダプタから呼ばれる。
#
# 終了コード:
#   0 = pass  (受け入れ基準内。stdout に集計を出力)
#   1 = block (要リライト。stdout に集計を出力)
#   2 = 判定不能(npx 失敗・JSON 不正など。アダプタは素通しにする)
#   3 = skip  (対象外: .md でない・日本語なし・opt-out 指定・本文なし)
#
# stdout (終了コード 0/1 のとき):
#   double_negative=<A(二重否定)の件数>
#   total=<総件数。ai-tech-writing-guideline の総括行は除く>
#   summary=<L<line>:<ruleId> を最大 15 件>
#
# 設定の解決順: $MEISEKI_LINT_CONFIG > このスクリプト位置からの既定パス
set -u

FILE="${1:-}"
[ -n "$FILE" ] || exit 3
case "$FILE" in
  *.md) ;;
  *) exit 3 ;;
esac
[ -f "$FILE" ] || exit 3

# 日本語(ひらがな・カタカナ・漢字)を含まないファイルは対象外
grep -q '[ぁ-んァ-ヶ一-龯]' "$FILE" 2>/dev/null || exit 3

# ファイル単位 opt-out(frontmatter は先頭 30 行の簡易判定、マーカーは全文有効)
if head -n 30 "$FILE" 2>/dev/null | grep -qE '^meiseki:[[:space:]]*(skip|false)[[:space:]]*$' \
   || grep -qE '<!--[[:space:]]*meiseki-disable[[:space:]]*-->' "$FILE" 2>/dev/null; then
  exit 3
fi

CORE_DIR=$(cd "$(dirname "$0")" && pwd)
CONFIG="${MEISEKI_LINT_CONFIG:-$CORE_DIR/../.agents/skills/meiseki/references/textlint.config.json}"
[ -f "$CONFIG" ] || exit 2

# ---- 対象外領域のマスキング(SKILL.md §3 の決定論層実装) ----
# 対象外領域を空行に置換した一時コピーを lint する。空行置換なので
# 行番号は原文とずれず、summary の "L<line>" をそのまま使える。
# 参考文献はセクション丸ごとマスクするため、エントリのフォーマット
# (Nature / ASA / APA / IEEE / 和文)に依存しない。
MASKED=$(mktemp "${TMPDIR:-/tmp}/meiseki-mask.XXXXXX") || exit 2
MASKED_MD="${MASKED}.md"
trap 'rm -f "$MASKED" "$MASKED_MD"' EXIT

awk '
BEGIN {
  in_fence = 0; in_math = 0; in_latex = 0; in_refs = 0; fence = ""
  # 参考文献セクションの見出し(表記ゆれはここに追加する。tolower 済みの行と比較)
  refs = "^#+[[:space:]]*(参考文献|参照文献|引用文献|文献リスト|文献|参考資料|references?|bibliography|works[[:space:]]+cited|citations)[[:space:]]*$"
}
{
  line = $0

  # 1) コードフェンス(mermaid のフローチャート等もここでマスクされる)
  if (in_fence) { print ""; if (line ~ ("^[[:space:]]*" fence)) in_fence = 0; next }
  if (line ~ /^[[:space:]]*```/) { in_fence = 1; fence = "```"; print ""; next }
  if (line ~ /^[[:space:]]*~~~/)  { in_fence = 1; fence = "~~~"; print ""; next }

  # 2) ブロック数式($$ ... $$ / \begin{...} ... \end{...})
  if (in_math) { print ""; if (line ~ /^[[:space:]]*\$\$[[:space:]]*$/) in_math = 0; next }
  if (line ~ /^[[:space:]]*\$\$[[:space:]]*$/) { in_math = 1; print ""; next }
  if (in_latex) { print ""; if (line ~ /\\end\{/) in_latex = 0; next }
  if (line ~ /\\begin\{(equation|align|alignat|gather|multline|eqnarray|math|displaymath|cases|split|array|matrix|pmatrix|bmatrix)\*?\}/) {
    if (line !~ /\\end\{/) in_latex = 1
    print ""; next
  }

  # 4) 参考文献セクション(見出しから次の見出しまで。フォーマット非依存)
  if (in_refs) {
    if (line ~ /^#/ && tolower(line) !~ refs) { in_refs = 0 }
    else { print ""; next }
  }
  if (tolower(line) ~ refs) { in_refs = 1; print ""; next }

  # 見出しなしで本文に混ざる文献行: IEEE 形式 "[1] ..." / 脚注定義 "[^1]: ..."
  if (line ~ /^[[:space:]]*\[[0-9]+\][[:space:]]/) { print ""; next }
  if (line ~ /^\[\^[^]]+\]:/) { print ""; next }

  # 5) 図表キャプション行(番号の直後に区切り記号がある行だけ。
  #    「図3に示すように〜」のような地の文は区切りがないのでマスクしない)
  if (line ~ /^[[:space:]]*(図|表)([0-9]|０|１|２|３|４|５|６|７|８|９)+[[:space:]]*(:|：|\.|．)/) { print ""; next }
  if (line ~ /^[[:space:]]*(Figure|Fig\.|Table)[[:space:]]*[0-9]+[[:space:]]*(:|：|\.|．)/) { print ""; next }

  # 6) 引用ブロック(SKILL.md §3「引用は原文のまま」) / 7) 画像行
  if (line ~ /^[[:space:]]*>/) { print ""; next }
  if (line ~ /^[[:space:]]*!\[/) { print ""; next }

  # 3) インライン数式($$...$$ → $...$ → \(...\) の順に除去)
  gsub(/\$\$[^$]+\$\$/, "", line)
  gsub(/\$[^$]+\$/, "", line)
  while ((i = index(line, "\\(")) > 0) {
    rest = substr(line, i + 2)
    j = index(rest, "\\)")
    if (j == 0) break
    line = substr(line, 1, i - 1) substr(rest, j + 2)
  }
  print line
}
' "$FILE" > "$MASKED_MD" 2>/dev/null || cp "$FILE" "$MASKED_MD"

# マスク後に日本語が残らなければ本文に検査対象がない
grep -q '[ぁ-んァ-ヶ一-龯]' "$MASKED_MD" 2>/dev/null || exit 3

# SKILL.md Step 2 と同一のピン止めバージョンで textlint を実行(指摘ありだと exit 1)
RESULT=$(npx --min-release-age=7 --yes \
  --package textlint@14.8.4 \
  --package textlint-rule-preset-ja-technical-writing@10.0.2 \
  --package textlint-rule-preset-ai-writing@1.1.0 \
  --package textlint-rule-prh@6.1.0 \
  textlint -c "$CONFIG" -f json "$MASKED_MD" 2>/dev/null)

# JSON が取れなければ(オフライン・npx 失敗など)判定不能
printf '%s' "$RESULT" | jq -e 'type == "array"' >/dev/null 2>&1 || exit 2

# G2(空虚な形容)・G3(空虚な動詞)も従来どおり集計に含める。学術文書の本文でも
# 曖昧な表現は直す対象であり、術語として実質を持つ語を残す判断はスキル層が行う。
DOUBLE_NEG=$(printf '%s' "$RESULT" | jq '[.[].messages[]? | select((.ruleId // "") | endswith("no-double-negative-ja"))] | length')
# ai-tech-writing-guideline の総括行(【テクニカルライティング品質分析】…)は
# 個別指摘の集計メッセージなので件数に数えない(SKILL.md §7)
TOTAL=$(printf '%s' "$RESULT" | jq '[.[].messages[]? | select((.message // "") | startswith("【テクニカルライティング品質分析】") | not)] | length')
SUMMARY=$(printf '%s' "$RESULT" | jq -r '[.[].messages[]? | select((.message // "") | startswith("【テクニカルライティング品質分析】") | not) | "L\(.line):\(.ruleId // "?")"] | .[0:15] | join(", ")')

printf 'double_negative=%s\n' "$DOUBLE_NEG"
printf 'total=%s\n' "$TOTAL"
printf 'summary=%s\n' "$SUMMARY"

# 受け入れ基準(SKILL.md §7): A(二重否定)は原則 0 件。軽微な指摘のみなら通す
if [ "$DOUBLE_NEG" -eq 0 ] && [ "$TOTAL" -lt 3 ]; then
  exit 0
fi
exit 1

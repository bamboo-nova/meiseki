#!/usr/bin/env bash
# meiseki PostToolUse hook:
# Write/Edit された日本語 Markdown を textlint(meiseki の決定論層)で検査し、
# 読解負荷が高ければ decision:"block" で Claude に meiseki スキルの適用を要求する。
#
# SKILL.md §3 の対象外領域(コード・数式・引用・参考文献・図表キャプション)は
# lint 前に空行へマスクし、判定は本文(地の文)のみで行う。
# 再実行ガード: 内容ハッシュ入りのステート TSV を npx 実行前に参照し、
# 同一内容の再 lint と block ループを抑止する。
#
# 無効化:
#   - 全体      : 環境変数 MEISEKI_HOOK_DISABLE=1
#   - ファイル単位: frontmatter に "meiseki: skip"、または本文のどこかに
#                 <!-- meiseki-disable --> マーカー
set -u

INPUT=$(cat)

[ "${MEISEKI_HOOK_DISABLE:-0}" = "1" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
SESSION=$(printf '%s' "$INPUT" | jq -r '.session_id // "default"' | tr -cd 'A-Za-z0-9._-')

[ -n "$FILE" ] || exit 0
case "$FILE" in
  *.md) ;;
  *) exit 0 ;;
esac
[ -f "$FILE" ] || exit 0

# 文書系 md 以外は対象外(設定・メモリ・計画・一時ファイル・フィクスチャ類)
case "$FILE" in
  */CLAUDE.md | */AGENTS.md | */MEMORY.md | */SKILL.md | \
  */.claude/* | */plans/* | */memory/* | */node_modules/* | */.git/* | \
  */scratchpad/* | /tmp/* | /private/tmp/* | /var/folders/* | \
  */examples/* | */references/*)
    exit 0 ;;
esac

# 日本語(ひらがな・カタカナ・漢字)を含まないファイルは対象外
grep -q '[ぁ-んァ-ヶ一-龯]' "$FILE" 2>/dev/null || exit 0

# ファイル単位 opt-out(frontmatter は先頭 30 行の簡易判定、マーカーは全文有効)
if head -n 30 "$FILE" 2>/dev/null | grep -qE '^meiseki:[[:space:]]*(skip|false)[[:space:]]*$' \
   || grep -qE '<!--[[:space:]]*meiseki-disable[[:space:]]*-->' "$FILE" 2>/dev/null; then
  exit 0
fi

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CONFIG="$PLUGIN_ROOT/skills/meiseki/references/textlint.config.json"
[ -f "$CONFIG" ] || exit 0

# ---- 再実行ガード(すべて npx 実行前) ----
# ステート TSV(1 行 = SESSION FILE HASH DECISION TOTAL DN SUMMARY)
STATE="${MEISEKI_HOOK_STATE:-${TMPDIR:-/tmp}/meiseki-hook-state.tsv}"
HASH=$(shasum -a 256 "$FILE" 2>/dev/null | cut -d' ' -f1)
[ -n "$HASH" ] || HASH=nohash

emit_advisory() { # total summary
  jq -n --arg ctx "meiseki hook: ${FILE} に textlint の指摘が $1 件残っています($2)。meiseki のガードレールに基づく文脈判断で意図的に残した指摘であれば、対応は不要です。" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
}

emit_block() { # dn total summary
  jq -n \
    --arg file "$FILE" \
    --arg dn "$1" \
    --arg total "$2" \
    --arg summary "$3" \
    '{decision: "block", reason: "meiseki hook: \($file) は読解負荷の高い構文を含みます(二重否定 \($dn) 件を含む計 \($total) 件)。meiseki スキル(plugin: meiseki)を必ず呼び出し、SKILL.md のワークフロー(意味把握 → patterns.md A→H でリライト → 意味の検算 → やりすぎチェック)に従ってこのファイルをリライトしてから作業を続けてください。textlint の指摘: \($summary)"}'
}

append_state() { # decision total dn summary
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$SESSION" "$FILE" "$HASH" "$1" "$2" "$3" "$(printf '%s' "$4" | tr '\t' ' ')" >> "$STATE"
}

BLOCKS=0
if [ -f "$STATE" ]; then
  BLOCKS=$(awk -F'\t' -v s="$SESSION" -v f="$FILE" \
    'BEGIN{c=0} $1==s && $2==f && $4=="block"{c++} END{print c}' "$STATE")

  # (1) 同一セッション・同一ファイル・同一内容 → 前回判定をリプレイ(再 lint しない)
  PREV=$(awk -F'\t' -v s="$SESSION" -v f="$FILE" -v h="$HASH" \
    '$1==s && $2==f && $3==h{l=$0} END{print l}' "$STATE")
  if [ -n "$PREV" ]; then
    if [ "$(printf '%s' "$PREV" | cut -f4)" = "pass" ]; then
      exit 0
    fi
    P_TOTAL=$(printf '%s' "$PREV" | cut -f5)
    P_DN=$(printf '%s' "$PREV" | cut -f6)
    P_SUM=$(printf '%s' "$PREV" | cut -f7)
    if [ "$BLOCKS" -ge 2 ]; then
      emit_advisory "$P_TOTAL" "$P_SUM"
      exit 0
    fi
    append_state block "$P_TOTAL" "$P_DN" "$P_SUM"
    emit_block "$P_DN" "$P_TOTAL" "$P_SUM"
    exit 0
  fi

  # (2) 別セッションが同一ファイル・同一内容を block 済み → advisory のみ
  #     (セッション再起動・コンテキスト圧縮後の再 block ループを遮断)
  XPREV=$(awk -F'\t' -v s="$SESSION" -v f="$FILE" -v h="$HASH" \
    '$1!=s && $2==f && $3==h && $4=="block"{l=$0} END{print l}' "$STATE")
  if [ -n "$XPREV" ]; then
    emit_advisory "$(printf '%s' "$XPREV" | cut -f5)" "$(printf '%s' "$XPREV" | cut -f7)"
    exit 0
  fi

  # (3) 同一セッション・同一ファイルの block が上限(2 回)到達 → lint せず advisory
  if [ "$BLOCKS" -ge 2 ]; then
    LASTB=$(awk -F'\t' -v s="$SESSION" -v f="$FILE" \
      '$1==s && $2==f && $4=="block"{l=$0} END{print l}' "$STATE")
    emit_advisory "$(printf '%s' "$LASTB" | cut -f5)" "$(printf '%s' "$LASTB" | cut -f7)"
    exit 0
  fi
fi

# ---- 対象外領域のマスキング(SKILL.md §3 のフック側実装) ----
# 対象外領域を空行に置換した一時コピーを lint する。空行置換なので
# 行番号は原文とずれず、block 理由の "L<line>" をそのまま使える。
# 参考文献はセクション丸ごとマスクするため、エントリのフォーマット
# (Nature / ASA / APA / IEEE / 和文)に依存しない。
MASKED=$(mktemp "${TMPDIR:-/tmp}/meiseki-mask.XXXXXX") || exit 0
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
grep -q '[ぁ-んァ-ヶ一-龯]' "$MASKED_MD" 2>/dev/null || exit 0

# SKILL.md Step 2 と同一のピン止めバージョンで textlint を実行(指摘ありだと exit 1)
RESULT=$(npx --min-release-age=7 --yes \
  --package textlint@14.8.4 \
  --package textlint-rule-preset-ja-technical-writing@10.0.2 \
  --package textlint-rule-prh@6.1.0 \
  textlint -c "$CONFIG" -f json "$MASKED_MD" 2>/dev/null)

# JSON が取れなければ(オフライン・npx 失敗など)書き込みを妨げない
printf '%s' "$RESULT" | jq -e 'type == "array"' >/dev/null 2>&1 || exit 0

# G2(空虚な形容)・G3(空虚な動詞)も従来どおり集計に含める。学術文書の本文でも
# 曖昧な表現は直す対象であり、術語として実質を持つ語を残す判断はスキル層が行う。
DOUBLE_NEG=$(printf '%s' "$RESULT" | jq '[.[].messages[]? | select((.ruleId // "") | endswith("no-double-negative-ja"))] | length')
TOTAL=$(printf '%s' "$RESULT" | jq '[.[].messages[]?] | length')

# 受け入れ基準(SKILL.md §7): A(二重否定)は原則 0 件。軽微な指摘のみなら通す
if [ "$DOUBLE_NEG" -eq 0 ] && [ "$TOTAL" -lt 3 ]; then
  append_state pass "$TOTAL" "$DOUBLE_NEG" "-"
  exit 0
fi

SUMMARY=$(printf '%s' "$RESULT" | jq -r '[.[].messages[]? | "L\(.line):\(.ruleId // "?")"] | .[0:15] | join(", ")')

append_state block "$TOTAL" "$DOUBLE_NEG" "$SUMMARY"
emit_block "$DOUBLE_NEG" "$TOTAL" "$SUMMARY"
exit 0

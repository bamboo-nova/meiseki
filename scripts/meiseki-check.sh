#!/usr/bin/env bash
# meiseki PostToolUse hook:
# Write/Edit された日本語 Markdown を textlint(meiseki の決定論層)で検査し、
# 読解負荷が高ければ decision:"block" で Claude に meiseki スキルの適用を要求する。
# 無効化: 環境変数 MEISEKI_HOOK_DISABLE=1
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

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CONFIG="$PLUGIN_ROOT/skills/meiseki/references/textlint.config.json"
[ -f "$CONFIG" ] || exit 0

# SKILL.md Step 2 と同一のピン止めバージョンで textlint を実行(指摘ありだと exit 1)
RESULT=$(npx --min-release-age=7 --yes \
  --package textlint@14.8.4 \
  --package textlint-rule-preset-ja-technical-writing@10.0.2 \
  --package textlint-rule-prh@6.1.0 \
  textlint -c "$CONFIG" -f json "$FILE" 2>/dev/null)

# JSON が取れなければ(オフライン・npx 失敗など)書き込みを妨げない
printf '%s' "$RESULT" | jq -e 'type == "array"' >/dev/null 2>&1 || exit 0

DOUBLE_NEG=$(printf '%s' "$RESULT" | jq '[.[].messages[]? | select((.ruleId // "") | endswith("no-double-negative-ja"))] | length')
TOTAL=$(printf '%s' "$RESULT" | jq '[.[].messages[]?] | length')

# 受け入れ基準(SKILL.md §7): A(二重否定)は原則 0 件。軽微な指摘のみなら通す
if [ "$DOUBLE_NEG" -eq 0 ] && [ "$TOTAL" -lt 3 ]; then
  exit 0
fi

SUMMARY=$(printf '%s' "$RESULT" | jq -r '[.[].messages[]? | "L\(.line):\(.ruleId // "?")"] | .[0:15] | join(", ")')

# ループ防止: 同一セッション・同一ファイルの block は最大 2 回まで
STATE="${TMPDIR:-/tmp}/meiseki-hook-${SESSION}.txt"
COUNT=$(grep -cxF -- "$FILE" "$STATE" 2>/dev/null)
COUNT=${COUNT:-0}

if [ "$COUNT" -ge 2 ]; then
  jq -n --arg ctx "meiseki hook: ${FILE} に textlint の指摘が ${TOTAL} 件残っています(${SUMMARY})。meiseki のガードレールに基づく文脈判断で意図的に残した指摘であれば、対応は不要です。" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
  exit 0
fi

printf '%s\n' "$FILE" >> "$STATE"

jq -n \
  --arg file "$FILE" \
  --arg dn "$DOUBLE_NEG" \
  --arg total "$TOTAL" \
  --arg summary "$SUMMARY" \
  '{decision: "block", reason: "meiseki hook: \($file) は読解負荷の高い構文を含みます(二重否定 \($dn) 件を含む計 \($total) 件)。meiseki スキル(plugin: meiseki)を必ず呼び出し、SKILL.md のワークフロー(意味把握 → patterns.md A→H でリライト → 意味の検算 → やりすぎチェック)に従ってこのファイルをリライトしてから作業を続けてください。textlint の指摘: \($summary)"}'
exit 0

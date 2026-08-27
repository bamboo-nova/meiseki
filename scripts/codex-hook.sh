#!/usr/bin/env bash
# meiseki PostToolUse hook (Codex CLI アダプタ):
# Codex のフックイベント JSON から編集されたファイルパスを取り出し、
# Claude Code アダプタ(meiseki-check.sh)に橋渡しする薄い変換層。
#
# Codex 0.149 系のフック仕様(実測):
#   - PostToolUse は apply_patch(ファイル編集)でも発火する。matcher は "Edit|Write" の
#     エイリアスも使えるが、tool_name は "apply_patch" のまま届く。
#   - ファイルパスは tool_input.file_path には入らず、tool_input.command(または input)の
#     apply_patch エンベロープ("*** Update File: <path>" 等)に埋まっている。
#   - 出力形式は Claude Code 互換({"decision":"block",...} / hookSpecificOutput)。
#
# 設定例(プロジェクトの .codex/hooks.json。フックは /hooks で trust が必要):
#   { "hooks": { "PostToolUse": [ { "matcher": "apply_patch|Edit|Write",
#     "hooks": [ { "type": "command", "command": "<絶対パス>/scripts/codex-hook.sh" } ] } ] } }
set -u

INPUT=$(cat)

[ "${MEISEKI_HOOK_DISABLE:-0}" = "1" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CHECK="$SCRIPT_DIR/meiseki-check.sh"
[ -f "$CHECK" ] || exit 0

SESSION=$(printf '%s' "$INPUT" | jq -r '.session_id // "codex"')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // "."')

# 編集されたファイルパスの抽出。
# 1) tool_input.file_path があればそれを使う(将来の正規化形式に備える)
# 2) なければ apply_patch エンベロープから "*** Add/Update File:" と "*** Move to:" を拾う
#    (Bash 経由の apply_patch ヒアドキュメントも command に同じエンベロープが入る)
PATHS=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
if [ -z "$PATHS" ]; then
  ENVELOPE=$(printf '%s' "$INPUT" | jq -r '
    (.tool_input.command // .tool_input.input // "")
    | if type == "array" then join("\n") else . end')
  PATHS=$(printf '%s\n' "$ENVELOPE" | sed -n \
    -e 's/^\*\*\* Add File: //p' \
    -e 's/^\*\*\* Update File: //p' \
    -e 's/^\*\*\* Move to: //p')
fi
[ -n "$PATHS" ] || exit 0

# ファイルごとに Claude Code 形式の入力を合成して meiseki-check.sh に渡す。
# 出力は 1 つしか返せないため、最初の block を優先し、なければ最初の advisory を返す。
BLOCK_OUT=""
ADVISORY_OUT=""
while IFS= read -r p; do
  [ -n "$p" ] || continue
  case "$p" in
    /*) abs="$p" ;;
    *)  abs="$CWD/$p" ;;
  esac
  [ -f "$abs" ] || continue
  OUT=$(jq -n --arg s "$SESSION" --arg f "$abs" \
        '{session_id: $s, tool_input: {file_path: $f}}' | "$CHECK")
  [ -n "$OUT" ] || continue
  if [ -z "$BLOCK_OUT" ] && printf '%s' "$OUT" | jq -e '.decision == "block"' >/dev/null 2>&1; then
    BLOCK_OUT="$OUT"
  elif [ -z "$ADVISORY_OUT" ]; then
    ADVISORY_OUT="$OUT"
  fi
done <<EOF
$PATHS
EOF

if [ -n "$BLOCK_OUT" ]; then
  printf '%s\n' "$BLOCK_OUT"
elif [ -n "$ADVISORY_OUT" ]; then
  printf '%s\n' "$ADVISORY_OUT"
fi
exit 0

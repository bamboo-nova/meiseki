#!/usr/bin/env bash
# meiseki PostToolUse hook (Claude Code アダプタ):
# Write/Edit された日本語 Markdown を meiseki-lint-core.sh(決定論層コア)で検査し、
# 読解負荷が高ければ decision:"block" で Claude に meiseki スキルの適用を要求する。
#
# 対象判定(日本語・opt-out)・マスキング・textlint 実行・閾値判定はコアが担う。
# このアダプタは Claude Code 固有の関心事だけを持つ:
#   - PostToolUse の JSON 入出力
#   - 文書系 md 以外の除外(設定・メモリ・計画・一時ファイル・フィクスチャ類)
#   - 再実行ガード: 内容ハッシュ入りのステート TSV で同一内容の再 lint と
#     block ループ(上限 2 回 → advisory 降格)を抑止する
#
# 無効化:
#   - 全体      : 環境変数 MEISEKI_HOOK_DISABLE=1
#   - ファイル単位: frontmatter に "meiseki: skip"、または本文のどこかに
#                 <!-- meiseki-disable --> マーカー(コアが判定)
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

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CORE="$SCRIPT_DIR/meiseki-lint-core.sh"
[ -f "$CORE" ] || exit 0

# ---- 再実行ガード(すべてコア実行前) ----
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

# ---- コア実行 ----
OUT=$(MEISEKI_LINT_CONFIG="${MEISEKI_LINT_CONFIG:-}" "$CORE" "$FILE")
RC=$?
# 2=判定不能(オフライン等) / 3=対象外 は書き込みを妨げない
[ "$RC" = "0" ] || [ "$RC" = "1" ] || exit 0

DOUBLE_NEG=$(printf '%s\n' "$OUT" | sed -n 's/^double_negative=//p')
TOTAL=$(printf '%s\n' "$OUT" | sed -n 's/^total=//p')
SUMMARY=$(printf '%s\n' "$OUT" | sed -n 's/^summary=//p')

if [ "$RC" = "0" ]; then
  append_state pass "$TOTAL" "$DOUBLE_NEG" "-"
  exit 0
fi

append_state block "$TOTAL" "$DOUBLE_NEG" "$SUMMARY"
emit_block "$DOUBLE_NEG" "$TOTAL" "$SUMMARY"
exit 0

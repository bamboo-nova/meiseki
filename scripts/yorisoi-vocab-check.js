#!/usr/bin/env node
// yorisoi-vocab-check.js — リポジトリ用ラッパー。
// 本体はスキル同梱の .agents/skills/yorisoi/scripts/vocab-check.js にある
// (スキル単体配布 `npx skills add --skill yorisoi` でも動くようにするため)。
// 使い方は本体と同じ: node scripts/yorisoi-vocab-check.js [--level N4] <file.md>
require(require('path').join(__dirname, '..', '.agents', 'skills', 'yorisoi', 'scripts', 'vocab-check.js'));

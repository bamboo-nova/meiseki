#!/usr/bin/env node
// meiseki-invariants.js — リポジトリ用ラッパー。
// 本体はスキル同梱の .agents/skills/meiseki/scripts/meiseki-invariants.js にある
// (スキル単体配布 `npx skills add --skill meiseki` でも動くようにするため)。
// 使い方は本体と同じ: node scripts/meiseki-invariants.js --before 前.md --after 後.md [--json]
'use strict';
const mod = require(require('path').join(__dirname, '..', '.agents', 'skills', 'meiseki', 'scripts', 'meiseki-invariants.js'));
module.exports = mod;
if (require.main === module) process.exitCode = mod.main();

#!/usr/bin/env node
// meiseki-invariants.js(意味の検算)のテスト。依存ゼロ。
// 実行: npm run test:meaning  (または node scripts/test-meaning.js)。例は examples/meaning/
//
//   Part 1: 意味を保った書き換え(examples/meiseki の 9 組と、文の分割)で恐れありが出ないこと
//   Part 2: 意味を変えた書き換え(否定の反転・数値・条件・確度・識別子・コード・範囲)をすべて検出すること
//   Part 3: 恐れありの段落だけを原文に戻すこと(--revert-risky / --keep)
//   Part 4: 同一の文書で何も出ないこと・終了コード
'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SCRIPT = path.join(ROOT, 'scripts', 'meiseki-invariants.js');
const FIX = path.join(ROOT, 'examples', 'meaning');
const EX = path.join(ROOT, 'examples', 'meiseki');

let pass = 0, fail = 0;
const ok = (d) => { pass++; console.log(`  ok  - ${d}`); };
const ng = (d) => { fail++; console.log(`  NG  - ${d}`); };
const check = (cond, d) => (cond ? ok(d) : ng(d));

function run(before, after, extra = []) {
  const r = spawnSync(process.execPath, [SCRIPT, '--before', before, '--after', after, '--json', ...extra], { encoding: 'utf8' });
  let json = null;
  try { json = JSON.parse(r.stdout); } catch (_) { /* 終了コード 2/3 では JSON を出さない */ }
  return { code: r.status, json };
}
const risks = (j) => (j ? j.findings.filter((f) => f.severity === 'risk') : []);

console.log('Part 1: 意味を保った書き換え');
const legit = fs.readdirSync(EX).filter((f) => f.endsWith('.before.md')).map((f) => path.join(EX, f));
legit.push(path.join(FIX, '08-split-legit.before.md'));
for (const b of legit) {
  const r = run(b, b.replace('.before.md', '.after.md'));
  check(r.code === 0 && risks(r.json).length === 0, `${path.basename(b, '.before.md')}: 恐れあり 0 件(exit=${r.code}, risk=${risks(r.json).length})`);
}

console.log('Part 2: 意味を変えた書き換え');
const expected = {
  '01-negation-flip': 'NEG',
  '02-number-change': 'N',
  '03-condition-drop': 'C',
  '04-hedge-strengthen': 'M',
  '05-identifier-change': 'I',
  '06-inline-code-change': 'P',
  '07-scope-widen': 'M',
};
for (const [name, cat] of Object.entries(expected)) {
  const r = run(path.join(FIX, `${name}.before.md`), path.join(FIX, `${name}.after.md`));
  const cats = risks(r.json).map((f) => f.category);
  check(r.code === 1 && cats.includes(cat), `${name}: ${cat} を恐れありとして検出(exit=${r.code}, 検出=${cats.join(',') || 'なし'})`);
}

console.log('Part 3: 原文に戻す');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'meiseki-meaning-'));
try {
  const out = path.join(tmp, 'final.md');
  const b = path.join(FIX, '09-revert.before.md'), a = path.join(FIX, '09-revert.after.md');
  let r = run(b, a, ['--revert-risky', '--out', out]);
  const expect = fs.readFileSync(path.join(FIX, '09-revert.expected.md'), 'utf8');
  check(r.code === 0 && fs.readFileSync(out, 'utf8') === expect, '恐れありの段落だけが原文に戻り、正しく書き換えた段落は残る');
  const r2 = run(b, out);
  check(r2.code === 0 && risks(r2.json).length === 0, '戻したあとの本文を原文と比べ直すと恐れあり 0 件');
  const ids = risks(run(b, a).json).map((f) => f.id).join(',');
  r = run(b, a, ['--revert-risky', '--out', out, '--keep', ids]);
  check(r.code === 0 && fs.readFileSync(out, 'utf8') === fs.readFileSync(a, 'utf8'), '--keep で外した指摘は戻さない');
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}

console.log('Part 4: 同一文書・終了コード');
for (const f of ['README.md', 'README.en.md']) {
  const p = path.join(ROOT, f);
  const r = run(p, p);
  check(r.code === 0 && r.json && r.json.findings.length === 0, `${f} を自分自身と比べて指摘 0 件`);
}
const tmp2 = fs.mkdtempSync(path.join(os.tmpdir(), 'meiseki-meaning-'));
try {
  const en = path.join(tmp2, 'en.md');
  fs.writeFileSync(en, 'This document has no Japanese text.\n');
  check(run(en, en).code === 3, '日本語のない文書は対象外(exit=3)');
  check(run(path.join(tmp2, 'missing.md'), en).code === 2, '読めないファイルは判定不能(exit=2)');
} finally {
  fs.rmSync(tmp2, { recursive: true, force: true });
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);

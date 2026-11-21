#!/usr/bin/env node
// 意味の検算(meiseki-invariants.js)の所要時間を測る。依存ゼロ。
// 実行: npm run bench:meaning  [-- --runs 5] [-- --no-textlint] [-- --save experiments/meaning-benchmark/results.json]
//
// スキルが実際に呼ぶ形(node のプロセス起動込み)で測る。比較の基準として、同じ文書に対する
// textlint 1 回分(既存のワークフローで書き換えの前後に 1 回ずつ必ず走る処理)も測る。
'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SCRIPT = path.join(ROOT, 'scripts', 'meiseki-invariants.js');
const args = process.argv.slice(2);
const RUNS = Number(args[args.indexOf('--runs') + 1]) || 5;
const WITH_TEXTLINT = !args.includes('--no-textlint');
const SAVE = args.includes('--save') ? args[args.indexOf('--save') + 1] : null;

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); const n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; };
function time(cmd, argv) {
  const t0 = process.hrtime.bigint();
  const r = spawnSync(cmd, argv, { encoding: 'utf8', cwd: ROOT, maxBuffer: 64 << 20 });
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  return { ms, code: r.status };
}

// 書き換え後の版を機械的に作る: 本文の段落だけに削除・分割・語の書き換えを混ぜ、対応づけに負荷をかける。
// コードブロックなどの保護ブロックはそのまま残す(空行で単純に区切ると、コードブロックの途中を壊してしまうため)
const { splitBlocks } = require('./meiseki-invariants.js');
function mutate(text) {
  const { blocks } = splitBlocks(text);
  const out = [];
  let n = 0;
  for (const b of blocks) {
    if (b.kind !== 'prose' || /^#/.test(b.text)) { out.push(b.text); continue; }
    n++;
    if (n % 11 === 5) continue; // 削除
    const q = b.text.replace(/することができます/g, 'できます').replace(/することができる/g, 'できる').replace(/を行う/g, 'する');
    const k = q.indexOf('。') + 1;
    if (n % 7 === 3 && k > 0 && k < q.length) { out.push(q.slice(0, k), q.slice(k).trim()); continue; } // 分割
    out.push(q);
  }
  return out.join('\n\n');
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'meiseki-bench-meaning-'));
const cases = [];
try {
  // 1) 例文 9 組(短い文書)
  const EX = path.join(ROOT, 'examples', 'meiseki');
  const pairs = fs.readdirSync(EX).filter((f) => f.endsWith('.before.md')).map((f) => [path.join(EX, f), path.join(EX, f.replace('.before.md', '.after.md'))]);
  const exTimes = [];
  for (let r = 0; r < RUNS; r++) for (const [b, a] of pairs) exTimes.push(time(process.execPath, [SCRIPT, '--before', b, '--after', a]).ms);
  const exChars = Math.round(pairs.reduce((s, [b]) => s + fs.readFileSync(b, 'utf8').length, 0) / pairs.length);
  cases.push({ name: 'examples/meiseki 9 組(1 組あたり)', chars: exChars, median_ms: median(exTimes), max_ms: Math.max(...exTimes), file: pairs[0][0] });

  // 2) README 相当と、それを連結した大きな文書
  const base = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8');
  for (const [label, k] of [['README.md 相当', 1], ['README ×4', 4], ['README ×10', 10]]) {
    const before = Array(k).fill(base).join('\n\n');
    const bf = path.join(tmp, `b${k}.md`), af = path.join(tmp, `a${k}.md`);
    fs.writeFileSync(bf, before); fs.writeFileSync(af, mutate(before));
    const ts = [];
    for (let r = 0; r < RUNS; r++) ts.push(time(process.execPath, [SCRIPT, '--before', bf, '--after', af]).ms);
    cases.push({ name: label, chars: before.length, paragraphs: before.split(/\n{2,}/).length, median_ms: median(ts), max_ms: Math.max(...ts), file: bf });
  }

  // 3) 基準: 同じ文書に対する textlint 1 回(既存の処理。npx のキャッシュが温まった状態で測る)
  if (WITH_TEXTLINT) {
    const pkgs = ['textlint@15.8.0', 'textlint-rule-preset-ja-technical-writing@12.0.2', 'textlint-rule-preset-ai-writing@1.1.0', 'textlint-rule-prh@6.1.1'];
    const cfg = path.join(ROOT, '.agents', 'skills', 'meiseki', 'references', 'textlint.config.json');
    const lintArgs = (f) => ['--min-release-age=7', '--yes', ...pkgs.flatMap((p) => ['--package', p]), 'textlint', '-c', cfg, '-f', 'json', f];
    for (const c of cases) {
      time('npx', lintArgs(c.file)); // 温める
      const ts = [];
      for (let r = 0; r < Math.min(RUNS, 3); r++) ts.push(time('npx', lintArgs(c.file)).ms);
      c.textlint_median_ms = median(ts);
    }
  }
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}

const rows = cases.map((c) => ({
  case: c.name, chars: c.chars, paragraphs: c.paragraphs || null,
  check_median_ms: Math.round(c.median_ms), check_max_ms: Math.round(c.max_ms),
  textlint_median_ms: c.textlint_median_ms ? Math.round(c.textlint_median_ms) : null,
  ratio_to_textlint: c.textlint_median_ms ? +(c.median_ms / c.textlint_median_ms).toFixed(3) : null,
}));
console.log(`意味の検算の所要時間(node のプロセス起動込み・${RUNS} 回の中央値)`);
console.log('| 文書 | 文字数 | 検算(中央値/最大) | textlint 1 回 | 比 |');
console.log('|---|---:|---:|---:|---:|');
for (const r of rows) {
  console.log(`| ${r.case} | ${r.chars.toLocaleString()} | ${r.check_median_ms} / ${r.check_max_ms} ms | ${r.textlint_median_ms === null ? '-' : r.textlint_median_ms + ' ms'} | ${r.ratio_to_textlint === null ? '-' : (r.ratio_to_textlint * 100).toFixed(1) + '%'} |`);
}
if (SAVE) {
  const meta = { date: new Date().toISOString(), node: process.version, platform: `${os.platform()} ${os.release()}`, cpu: os.cpus()[0] && os.cpus()[0].model, runs: RUNS };
  fs.mkdirSync(path.dirname(path.resolve(ROOT, SAVE)), { recursive: true });
  fs.writeFileSync(path.resolve(ROOT, SAVE), JSON.stringify({ meta, rows }, null, 2) + '\n');
  console.log(`保存: ${SAVE}`);
}

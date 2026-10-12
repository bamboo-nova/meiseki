#!/usr/bin/env node
// bench-jev.js — Jev 判定層の速度と一致率を測る(npm run bench:jev)
//
// 判定セットは experiments/jev-benchmark/cases.json から読む(誰でも同じ条件で再現できる)。
// 既定は単問モード(1 問 = 1 リクエスト)。--batch で全問を 1 リクエストにまとめる
// 実運用形を測る。採用帯(p >= 0.8 / p <= 0.2)での採用数・採用正解率も表示する。
//
// 再現手順・過去の実測結果は experiments/jev-benchmark/README.md を参照。
// キー未設定(exit 3)・失敗(exit 2)のときはその旨を表示して終わる。

'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const CASES_PATH = process.env.JEV_BENCH_CASES ||
  path.join(__dirname, '..', 'experiments', 'jev-benchmark', 'cases.json');
const spec = JSON.parse(fs.readFileSync(CASES_PATH, 'utf8'));
const CASES = spec.cases;
const BAND = spec.adoption_band || { yes_min: 0.8, no_max: 0.2 };
const judge = path.join(__dirname, 'jev-judge.js');

function runJudge(req) {
  const r = spawnSync('node', [judge], { input: JSON.stringify(req), encoding: 'utf8', timeout: 30000 });
  return r;
}

function percentile(sorted, p) {
  const i = Math.min(sorted.length - 1, Math.floor(p * sorted.length));
  return sorted[i];
}

function classify(p) {
  // 採用帯: 確信の強い判定だけ採用し、不確信帯は LLM へ差し戻す
  if (p >= BAND.yes_min) return true;
  if (p <= BAND.no_max) return false;
  return null; // 差し戻し
}

function summarize(records) {
  const done = records.filter((r) => r.p !== null);
  const agree = done.filter((r) => (r.p >= 0.5) === r.expect).length;
  const adopted = done.filter((r) => classify(r.p) !== null);
  const adoptedOk = adopted.filter((r) => classify(r.p) === r.expect).length;
  const deferred = done.length - adopted.length;
  console.log('---');
  console.log(`生の一致率: ${agree}/${done.length} (${Math.round((agree / done.length) * 100)}%)`);
  console.log(`採用帯(p>=${BAND.yes_min} / p<=${BAND.no_max}): 採用 ${adopted.length} 問(正解 ${adoptedOk}/${adopted.length})、LLM へ差し戻し ${deferred} 問`);
}

(async () => {
  const batch = process.argv.includes('--batch');

  if (batch) {
    console.log(`bench:jev --batch — ${CASES.length} 問を 1 リクエストで判定(実運用形)`);
    const state = CASES.map((c) => `[${c.id}] ${c.state}`).join('\n\n');
    const questions = {};
    for (const c of CASES) {
      questions[c.id.replace(/-/g, '_')] = { type: 'noul', instructions: `[${c.id}] のテキストについて: ${c.instructions}` };
    }
    const r = runJudge({ state, questions });
    if (r.status === 3) { console.log('キー未設定のため測定できません。node scripts/jev-judge.js --setup でキーを保存してください。'); process.exit(3); }
    if (r.status !== 0) { console.log(`失敗(exit ${r.status})`); process.exit(2); }
    const body = JSON.parse(r.stdout);
    const records = CASES.map((c) => {
      const ans = body.answers[c.id.replace(/-/g, '_')];
      const p = ans && typeof ans.noul === 'number' ? ans.noul : (ans && typeof ans.noul === 'boolean' ? (ans.noul ? 1 : 0) : null);
      return { id: c.id, expect: c.expect, p };
    });
    for (const rec of records) {
      const got = rec.p === null ? '?' : rec.p >= 0.5;
      const hit = got === rec.expect ? '一致' : '不一致';
      const band = rec.p === null ? '' : (classify(rec.p) === null ? ' → 差し戻し' : ' → 採用');
      console.log(`  ${rec.id}: ${hit} (期待 ${rec.expect} / p=${rec.p === null ? '?' : rec.p.toFixed(2)})${band}`);
    }
    console.log(`レイテンシ: ${body._meta.elapsed_ms}ms(${CASES.length} 問一括)`);
    summarize(records);
    return;
  }

  console.log(`bench:jev — ${CASES.length} ケース(G/H/A)を 1 件ずつ判定(--batch で一括形も測れる)`);
  const times = [];
  const records = [];
  for (const c of CASES) {
    const r = runJudge({ state: c.state, questions: { q: { type: 'noul', instructions: c.instructions } } });
    if (r.status === 3) { console.log('キー未設定のため測定できません。node scripts/jev-judge.js --setup でキーを保存してください。'); process.exit(3); }
    if (r.status !== 0) { console.log(`  ${c.id}: 失敗(exit ${r.status}) — スキップ`); records.push({ id: c.id, expect: c.expect, p: null }); continue; }
    const body = JSON.parse(r.stdout);
    const ans = body.answers.q;
    const p = typeof ans.noul === 'number' ? ans.noul : (typeof ans.noul === 'boolean' ? (ans.noul ? 1 : 0) : null);
    const api_ms = body._meta.elapsed_ms;
    times.push(api_ms);
    records.push({ id: c.id, expect: c.expect, p });
    const hit = (p >= 0.5) === c.expect ? '一致' : '不一致';
    console.log(`  ${c.id}: ${hit} (期待 ${c.expect} / p=${p.toFixed(2)}) ${api_ms}ms`);
  }
  const done = times.length;
  if (!done) { console.log('有効な判定が得られませんでした。'); process.exit(2); }
  const sorted = [...times].sort((a, b) => a - b);
  const sum = times.reduce((a, b) => a + b, 0);
  console.log(`レイテンシ: 合計 ${sum}ms / 平均 ${Math.round(sum / done)}ms / p50 ${percentile(sorted, 0.5)}ms`);
  summarize(records);
})();

#!/usr/bin/env node
/*
 * vocab-check.js — やさしい日本語の語彙レベル判定(決定論層)
 *
 * 使い方:
 *   node vocab-check.js [--level N4] [--format text|json] [--jev <jev.csv>] <file.md>
 *
 * 出力: 目標レベルを超える語を行番号つきで報告する。
 *   - 「超過」  : 同梱の JLPT 推定リストで目標より難しいレベルに載っている語(確定扱い)
 *   - 「リスト外」: どのリストにも載っていない語(参考扱い。固有名詞は除外済み)
 *
 * 終了コード: 0=超過なし / 1=超過あり / 2=実行エラー
 *
 * 語彙リスト(references/vocab/):
 *   - jlpt-tanos.csv      : tanos.co.uk 由来の JLPT 推定リスト(CC BY)。公式リストは
 *                           2010 年以降非公開のため「N○相当」はすべて推定値。
 *   - kokugoken-basic.csv : 国語研『日本語教育のための基本語彙調査』(1984、CC BY 4.0)。
 *                           rank=2000(基本語二千) / 6000(基本語彙六千)。
 *   - jev.csv (任意)      : 日本語教育語彙表。二次配布禁止のため同梱しない。利用者が
 *                           自分で入手・変換して置いた場合だけ読む(level,expression,reading。
 *                           level は 1〜6 = 初級前半〜上級後半)。
 *
 * 形態素解析は kuromojin(kuromoji.js)を使う。未インストールなら初回に
 * キャッシュディレクトリへ自動インストールする(npx と同じく初回のみ数十秒)。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { createRequire } = require('module');

const KUROMOJIN_VERSION = '3.0.0';

// ---- 引数 ----
const args = process.argv.slice(2);
let level = 'N4';
let format = 'text';
let jevPath = null;
let file = null;
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === '--level') level = String(args[++i] || '').toUpperCase();
  else if (a === '--format') format = args[++i];
  else if (a === '--jev') jevPath = args[++i];
  else if (!a.startsWith('-')) file = a;
}
const LEVELS = ['N5', 'N4', 'N3', 'N2', 'N1'];
if (!file || !LEVELS.includes(level)) {
  console.error('usage: vocab-check.js [--level N5..N1] [--format text|json] [--jev jev.csv] <file.md>');
  process.exit(2);
}
const targetIdx = LEVELS.indexOf(level);
// JEV レベル(1〜6)との対応: N5→1, N4→2, N3→4, N2→5, N1→6
const JEV_MAX = { N5: 1, N4: 2, N3: 4, N2: 5, N1: 6 }[level];

// ---- kuromojin の解決(なければキャッシュへ自動インストール) ----
function loadKuromojin() {
  try {
    return require('kuromojin');
  } catch (_) { /* fallthrough */ }
  const cache = process.env.MEISEKI_VOCAB_CACHE
    || path.join(process.env.HOME || process.env.USERPROFILE || '.', '.cache', 'meiseki', 'vocab-deps');
  const mod = path.join(cache, 'node_modules', 'kuromojin');
  if (!fs.existsSync(mod)) {
    fs.mkdirSync(cache, { recursive: true });
    console.error(`vocab-check: kuromojin@${KUROMOJIN_VERSION} を ${cache} にインストールします(初回のみ)...`);
    execSync(`npm install --prefix "${cache}" --no-save --no-audit --no-fund --loglevel=error kuromojin@${KUROMOJIN_VERSION}`,
      { stdio: ['ignore', 'ignore', 'inherit'] });
  }
  return createRequire(path.join(cache, 'node_modules', 'x.js'))('kuromojin');
}

// ---- 語彙リストの読み込み ----
function parseCsvLine(line) {
  // 単純 CSV(フィールド内の引用符つきカンマに対応)
  const out = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQ) {
      if (ch === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else inQ = false; }
      else cur += ch;
    } else if (ch === '"') inQ = true;
    else if (ch === ',') { out.push(cur); cur = ''; }
    else cur += ch;
  }
  out.push(cur);
  return out;
}
function readCsv(p) {
  const rows = fs.readFileSync(p, 'utf8').split(/\r?\n/).filter(Boolean).map(parseCsvLine);
  rows.shift(); // ヘッダ
  return rows;
}
// tanos リストの見出しには "(花を〜) 生ける, 活ける" のような注記・併記がある。
// 括弧注記を除去し、カンマ・読点で分割して個々の語形に開く。
function cleanForms(s) {
  return s
    .replace(/[（(][^）)]*[）)]/g, ' ')
    .split(/[,、\/]/)
    .map((t) => t.replace(/[〜～\s]/g, ''))
    .filter((t) => t.length > 0);
}
const kataToHira = (s) => s.replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60));

const vocabDir = path.join(__dirname, '..', 'references', 'vocab');
const jlptByForm = new Map(); // 語形/読み → レベル index(易しい方を保持)
for (const [lv, expr, reading] of readCsv(path.join(vocabDir, 'jlpt-tanos.csv'))) {
  const idx = LEVELS.indexOf(lv);
  if (idx < 0) continue;
  for (const form of [...cleanForms(expr), ...cleanForms(kataToHira(reading))]) {
    const prev = jlptByForm.get(form);
    if (prev === undefined || idx < prev) jlptByForm.set(form, idx);
  }
}
const kokugoken = new Map(); // かな → rank(2000|6000)
for (const [kana, , rank] of readCsv(path.join(vocabDir, 'kokugoken-basic.csv'))) {
  const prev = kokugoken.get(kana);
  if (prev === undefined || rank === '2000') kokugoken.set(kana, rank);
}
let jev = null; // かな/語形 → JEV レベル(1〜6)
const jevFile = jevPath || path.join(vocabDir, 'jev.csv');
if (fs.existsSync(jevFile)) {
  jev = new Map();
  for (const [lv, expr, reading] of readCsv(jevFile)) {
    const n = parseInt(lv, 10);
    if (!(n >= 1 && n <= 6)) continue;
    for (const form of [...cleanForms(expr || ''), ...cleanForms(kataToHira(reading || ''))]) {
      const prev = jev.get(form);
      if (prev === undefined || n < prev) jev.set(form, n);
    }
  }
}

// ---- 対象外領域のマスキング(コード・引用・画像・リンク先・インラインコード) ----
function maskLines(text) {
  const lines = text.split(/\r?\n/);
  let inFence = false;
  return lines.map((line) => {
    if (inFence) { if (/^\s*(```|~~~)/.test(line)) inFence = false; return ''; }
    if (/^\s*(```|~~~)/.test(line)) { inFence = true; return ''; }
    if (/^\s*>/.test(line) || /^\s*!\[/.test(line)) return '';
    return line
      .replace(/`[^`]*`/g, ' ')
      .replace(/\]\([^)]*\)/g, '] ')
      .replace(/https?:\/\/\S+/g, ' ');
  });
}

// 定型表現の分解片など、語彙レベルを問わない機能語
const STOPWORDS = new Set(['しれる', 'とおり', 'ながら', 'および', 'また']);

// ---- 判定対象の品詞 ----
function isTarget(t) {
  const pos = t.pos;
  const d1 = t.pos_detail_1;
  if (pos === '名詞') {
    return !['固有名詞', '数', '代名詞', '非自立', '接尾', '接続詞的', '特殊'].includes(d1);
  }
  if (pos === '動詞' || pos === '形容詞') return d1 === '自立';
  if (pos === '副詞') return true;
  return false;
}

// ---- 語の判定 ----
function judge(base, readingHira) {
  const forms = [base, readingHira].filter(Boolean);
  // JEV があれば最優先(利用者が自分で入手した本命リスト)
  if (jev) {
    for (const f of forms) {
      const n = jev.get(f);
      if (n !== undefined) return n <= JEV_MAX ? null : { kind: 'over', label: `JEV レベル${n}` };
    }
  }
  let worst;
  for (const f of forms) {
    const idx = jlptByForm.get(f);
    if (idx !== undefined) {
      if (idx <= targetIdx) return null; // 目標レベル内
      if (worst === undefined || idx > worst) worst = idx;
    }
  }
  // 国語研: 基本語二千は常に許容。基本語彙六千は目標 N4 以上(難しい側)なら許容。
  // JLPT 推定リストが上位レベル判定でも、基本語彙に載っていれば許容側に倒す
  // (tanos リストのレベル付けは硬めに偏るため)。
  for (const f of forms) {
    const rank = kokugoken.get(f);
    if (rank === '2000') return null;
    if (rank === '6000' && targetIdx >= LEVELS.indexOf('N4')) return null;
  }
  if (worst !== undefined) return { kind: 'over', label: `${LEVELS[worst]}相当(推定)` };
  return { kind: 'unknown', label: 'リスト外' };
}

// ---- 実行 ----
(async () => {
  const text = fs.readFileSync(file, 'utf8');
  const lines = maskLines(text);
  const { tokenize } = loadKuromojin();

  const findings = new Map(); // base → {label,kind,lines:[],surface}
  // jReadability 参考値用の統計(李・長谷部の公開式。語種は表層から推定する近似)
  const st = { tokens: 0, kango: 0, wago: 0, verbs: 0, particles: 0, chars: 0, sentences: 0 };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!/[ぁ-んァ-ヶ一-龯]/.test(line)) continue;
    const body = line.replace(/^[\s#>*\-|]+/, '');
    st.chars += body.replace(/\s/g, '').length;
    st.sentences += (body.match(/[。！？!?]/g) || []).length;
    const tokens = await tokenize(line);
    for (const t of tokens) {
      if (t.pos !== '記号') {
        st.tokens++;
        if (t.pos === '動詞') st.verbs++;
        else if (t.pos === '助詞') st.particles++;
        if (/^[一-龯]{2,}$/.test(t.surface_form)) st.kango++;
        else if (/[ぁ-ん]/.test(t.surface_form) || /^[一-龯]$/.test(t.surface_form)) st.wago++;
      }
      if (!isTarget(t)) continue;
      const base = t.basic_form && t.basic_form !== '*' ? t.basic_form : t.surface_form;
      if (!/[ぁ-んァ-ヶ一-龯]/.test(base)) continue;
      if (base.length === 1 && /^[ぁ-ん]$/.test(base)) continue;
      if (STOPWORDS.has(base)) continue;
      const readingHira = t.reading && t.reading !== '*' ? kataToHira(t.reading) : null;
      const r = judge(base, readingHira);
      if (!r) continue;
      const cur = findings.get(base) || { ...r, surface: t.surface_form, lines: [] };
      cur.lines.push(i + 1);
      findings.set(base, cur);
    }
  }

  const over = [...findings.entries()].filter(([, v]) => v.kind === 'over');
  const unknown = [...findings.entries()].filter(([, v]) => v.kind === 'unknown');
  const fmt = ([base, v]) => `L${[...new Set(v.lines)].slice(0, 5).join(',L')}: ${base}(${v.label})`;

  // jReadability 公開式(李・長谷部): 平均文長×-0.056 + 漢語率×-0.126 + 和語率×-0.042
  //   + 動詞率×-0.145 + 助詞率×-0.044 + 11.724   (値が大きいほど易しい)
  // 本実装は IPADIC に語種情報がないため、漢語=2字以上の漢字連続語・和語=かな含み語と
  // 表層から推定した「近似値」。参考表示にとどめ、判定には使わない。
  let jread = null;
  if (st.sentences > 0 && st.tokens > 0) {
    const mean = st.chars / st.sentences;
    const pct = (n) => (n / st.tokens) * 100;
    jread = 11.724 - 0.056 * mean - 0.126 * pct(st.kango) - 0.042 * pct(st.wago)
      - 0.145 * pct(st.verbs) - 0.044 * pct(st.particles);
    jread = Math.round(jread * 100) / 100;
  }

  if (format === 'json') {
    console.log(JSON.stringify({
      file, level, jev: !!jev,
      over: over.map(([base, v]) => ({ word: base, label: v.label, lines: [...new Set(v.lines)] })),
      unknown: unknown.map(([base, v]) => ({ word: base, label: v.label, lines: [...new Set(v.lines)] })),
      jreadability_approx: jread,
    }, null, 2));
  } else {
    console.log(`vocab-check: 目標 ${level} / JEV ${jev ? 'あり' : 'なし(同梱リストのみ)'}`);
    console.log(`超過(確定扱い): ${over.length} 語`);
    for (const e of over) console.log('  ' + fmt(e));
    console.log(`リスト外(参考): ${unknown.length} 語`);
    for (const e of unknown) console.log('  ' + fmt(e));
    if (jread !== null) console.log(`jReadability 近似値(参考・高いほど易しい): ${jread}`);
  }
  process.exit(over.length > 0 ? 1 : 0);
})().catch((e) => { console.error('vocab-check: エラー:', e.message); process.exit(2); });

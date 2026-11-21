#!/usr/bin/env node
// meiseki-invariants.js — 書き換えの前後で「変わってはいけないもの」が変わっていないかを数えて比べる
// (依存ゼロ・Node 18+・オフライン)
//
// 意味が保たれたかの合否は決めない。印(数値・識別子・否定・条件・確度など)の増減を報告するだけで、
// 最終判断はスキル層(LLM)が原文と照らして行う。何も出なかったことは「意味が保たれた」ことを意味しない。
//
// 本体はスキル同梱のこのファイル(スキル単体配布 `npx skills add --skill meiseki` でも動くようにするため)。
// リポジトリ直下の scripts/meiseki-invariants.js は、これを呼ぶだけのラッパー。
//
// 使い方:
//   node <SKILL_DIR>/scripts/meiseki-invariants.js --before 前.md --after 後.md [--json]
//   node <SKILL_DIR>/scripts/meiseki-invariants.js --before 前.md --after 後.md --revert-risky --out 最終.md [--keep F2,F5]
//
//   --revert-risky  恐れありの段落を原文の段落に戻した本文を --out に書く(決定的な最後の安全装置)
//   --keep          正当と判断した指摘の id。戻す対象から外す(理由を報告できる場合だけ使う)
//
// 終了コード:
//   0 = 恐れなし(--revert-risky のときは、恐れありをすべて戻せた)
//   1 = 恐れあり(--revert-risky のときは、自動で戻せない恐れが残った)
//   2 = 判定不能(引数・ファイルの誤り)
//   3 = 対象外(書き換え前の本文に日本語がない)
'use strict';

const fs = require('fs');

// ---------------------------------------------------------------------------
// 引数
// ---------------------------------------------------------------------------
function parseArgs(argv) {
  const a = { before: null, after: null, json: false, revert: false, out: null, keep: new Set() };
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--before') a.before = argv[++i];
    else if (k === '--after') a.after = argv[++i];
    else if (k === '--json') a.json = true;
    else if (k === '--revert-risky') a.revert = true;
    else if (k === '--out') a.out = argv[++i];
    else if (k === '--keep') String(argv[++i] || '').split(',').map((s) => s.trim()).filter(Boolean).forEach((s) => a.keep.add(s));
    else return null;
  }
  if (!a.before || !a.after) return null;
  if (a.revert && !a.out) return null;
  return a;
}

// ---------------------------------------------------------------------------
// ブロック分割
//   保護ブロック: コードフェンス・ブロック数式・LaTeX 環境・引用・画像・参考文献・脚注定義・
//   文献行・図表キャプション・HTML コメント・front matter。
//   meiseki-lint-core.sh のマスキング対象と揃えている(書き換えてはいけない領域)。
//   本文ブロック: 空行で区切った段落。見出しは 1 行で 1 ブロック。リストや表は連続行で 1 ブロック。
// ---------------------------------------------------------------------------
const REFS_HEADING = /^#+\s*(参考文献|参照文献|引用文献|文献リスト|文献|参考資料|references?|bibliography|works\s+cited|citations)\s*$/i;
const LATEX_BEGIN = /\\begin\{(equation|align|alignat|gather|multline|eqnarray|math|displaymath|cases|split|array|matrix|pmatrix|bmatrix)\*?\}/;

function splitBlocks(text) {
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let i = 0;
  const push = (kind, s, e) => blocks.push({ kind, start: s, end: e, text: lines.slice(s, e + 1).join('\n') });

  // front matter
  if (lines[0] === '---') {
    let j = 1;
    while (j < lines.length && lines[j] !== '---') j++;
    if (j < lines.length) { push('protected', 0, j); i = j + 1; }
  }
  let inRefs = false;
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*$/.test(line)) { i++; continue; }
    // 参考文献セクション(見出しから次の見出しまで)
    if (REFS_HEADING.test(line)) { inRefs = true; push('protected', i, i); i++; continue; }
    if (inRefs) {
      if (/^#/.test(line)) inRefs = false;
      else { push('protected', i, i); i++; continue; }
    }
    const fence = line.match(/^\s*(```|~~~)/);
    if (fence) {
      let j = i + 1;
      while (j < lines.length && !new RegExp('^\\s*' + fence[1]).test(lines[j])) j++;
      push('protected', i, Math.min(j, lines.length - 1)); i = j + 1; continue;
    }
    if (/^\s*\$\$\s*$/.test(line)) {
      let j = i + 1;
      while (j < lines.length && !/^\s*\$\$\s*$/.test(lines[j])) j++;
      push('protected', i, Math.min(j, lines.length - 1)); i = j + 1; continue;
    }
    if (LATEX_BEGIN.test(line)) {
      let j = i;
      while (j < lines.length && !/\\end\{/.test(lines[j])) j++;
      push('protected', i, Math.min(j, lines.length - 1)); i = j + 1; continue;
    }
    if (/^\s*<!--/.test(line)) {
      let j = i;
      while (j < lines.length && !/-->/.test(lines[j])) j++;
      push('protected', i, Math.min(j, lines.length - 1)); i = j + 1; continue;
    }
    if (/^\s*>/.test(line)) {
      let j = i;
      while (j + 1 < lines.length && /^\s*>/.test(lines[j + 1])) j++;
      push('protected', i, j); i = j + 1; continue;
    }
    if (/^\s*!\[/.test(line) || /^\[\^[^\]]+\]:/.test(line) || /^\s*\[[0-9]+\]\s/.test(line)
      || /^\s*(図|表)[0-9０-９]+\s*[:：.．]/.test(line) || /^\s*(Figure|Fig\.|Table)\s*[0-9]+\s*[:：.．]/.test(line)) {
      push('protected', i, i); i++; continue;
    }
    if (/^#{1,6}\s/.test(line)) { push('prose', i, i); i++; continue; }
    // 本文: 空行・保護ブロックの開始・見出しまで
    let j = i;
    while (j + 1 < lines.length) {
      const nx = lines[j + 1];
      if (/^\s*$/.test(nx) || /^#{1,6}\s/.test(nx) || /^\s*(```|~~~|\$\$\s*$|>|!\[|<!--)/.test(nx) || LATEX_BEGIN.test(nx)) break;
      j++;
    }
    push('prose', i, j); i = j + 1;
  }
  return { lines, blocks };
}

// ---------------------------------------------------------------------------
// 本文ブロックから保護すべきインライン要素を抜き、印を数える
// ---------------------------------------------------------------------------
const toHalf = (s) => s.replace(/[０-９．，％]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xFEE0));

function extractInline(text) {
  const spans = [];
  let t = text;
  // インラインコード → インライン数式 → リンク先 → 裸の URL の順に抜く
  t = t.replace(/`[^`\n]+`/g, (m) => { spans.push(m); return ' '; });
  t = t.replace(/\$[^$\n]+\$/g, (m) => { spans.push(m); return ' '; });
  t = t.replace(/\]\(([^)\s]+)[^)]*\)/g, (m, u) => { spans.push(u); return '] '; });
  t = t.replace(/https?:\/\/[^\s)>\]」、。]+/g, (m) => { spans.push(m); return ' '; });
  t = t.replace(/<[^>\n]+>/g, ' '); // HTML タグは数えない
  return { spans, prose: t };
}

// 否定: 「ない」の活用・「ず」・「ません」・「否定」・否定の接頭辞を持つ一覧の語
// 「〜かねない/かねません」は形は否定でも意味は可能性なので、否定から外して可能性に数える
const NEG_EXCLUDE = /少な(?:い|く|かっ|け)|危な(?:い|く|かっ)|切な(?:い|く)|はかな(?:い|く)|なくな(?:る|り|っ|ら|れ)|かね(?:な[いく]|ません)|必ず|まず|わずか|はず/g;
const NEG = [
  /な(?:い|く|けれ|かっ|し(?=[でにのとは、。]))/g,
  /ず(?=[にとも、。]|して)/g,
  /ません/g,
  /否定/g,
  /不可能|不要|不可|不十分|不足|不明|不能|非対応|非推奨|無効|無理|未対応|未実装|未定/g,
];
// 条件・例外・限定(減少を恐れありとする)
const COND = {
  // 「〜すると、」「〜すれば」「〜したら、」も条件として数える(「場合」→「すると」の言い換えで誤検出しないため)
  condition: [
    /場合(?![がも](?:あ|多))/g, /とき(?!どき)/g, /(?<![実国交手間窓水])際(?=[にはの])/g, /(?<!に)なら(?:ば)?(?![なずべびぶうれ])/g,
    /(?<=[うくぐすつぬぶむるい])と(?=[、,])/g, /(?<=[えけげせてねべめれ])ば(?![かりっ])/g,
    /(?<=[っんいしちきぎみびりにえけせてねめれ])(?:たら|だら)(?=[、,]|ば)/g,
  ],
  exception: [/ただし|但し|を除[きいくけ]|以外|例外(?!なく)/g],
  limitation: [/のみ|だけ|に限[りっるら]|限定/g],
};
// 確度・義務・全称・部分(減少を恐れありとする)
const MODAL = {
  possibility: [/(?:こと|場合)(?:が|も)(?:あ|多)|かもしれ|可能性|おそれ|恐れ|(?:し|あり|起こり|なり)?得[るま]|かね(?:な[いく]|ません)|だろう|でしょう|と思われ|と考えられ/g],
  obligation: [/必要(?:が|で|だ|と|な)|必須|べき|なければな|なくてはな|ねばな/g],
  universal: [/すべて|全て|常に|必ず|いつも|例外なく|一切/g],
  partial: [/一部|多くの|ほとんど|大半|通常|一般に|たいてい|しばしば|ときどき|時々/g],
};
const CLASS_LABEL = {
  condition: '条件', exception: '例外', limitation: '限定',
  possibility: '可能性', obligation: '義務', universal: '全称', partial: '部分',
};

function matchAll(res, s) {
  const out = [];
  for (const re of res) { re.lastIndex = 0; let m; while ((m = re.exec(s))) out.push(m[0]); }
  return out;
}

const IDENT = /[A-Za-z][A-Za-z0-9_]*(?:[.\-/:][A-Za-z0-9_]+)*(?:\(\))?/g;
const NUM = /(約|およそ|最大|最小|少なくとも)?\s*([0-9]+(?:[.,][0-9]+)*)\s*(%|ms|秒|分|時間|日|週間|か月|ヶ月|年|件|個|回|倍|円|MB|GB|KB|TB|文字|字|行|人|台|本|点|ページ|px|つ)?(以上|以下|未満|超|程度|前後)?/g;
// 箇条書きの項目(項目数を数える。列挙を箇条書きに開いて「次の 4 つ」と書いた場合の判定に使う)
const LIST_ITEM = /^\s{0,3}(?:[-*+]|\d+[.)])\s/gm;
const QUOTED = /「([^「」\n]{1,40})」/g;

function analyzeProse(raw) {
  const { spans, prose } = extractInline(raw);
  // 見出し・リスト・表の記号は数えない
  let p = prose.replace(/^\s{0,3}(?:#{1,6}\s|[-*+]\s|\d+[.)]\s)/gm, ' ').replace(/[|*_~]/g, ' ');
  const idents = (p.match(IDENT) || []);
  const pNoIdent = toHalf(p.replace(IDENT, ' '));
  const nums = [];
  NUM.lastIndex = 0; let m;
  while ((m = NUM.exec(pNoIdent))) nums.push(`${m[1] || ''}${m[2]}${m[3] || ''}${m[4] || ''}`);
  const quoted = []; QUOTED.lastIndex = 0;
  while ((m = QUOTED.exec(p))) quoted.push(m[1]);
  const negSrc = p.replace(NEG_EXCLUDE, '＿');
  const neg = matchAll(NEG, negSrc);
  const cond = {}; for (const k of Object.keys(COND)) cond[k] = matchAll(COND[k], p);
  const modal = {}; for (const k of Object.keys(MODAL)) modal[k] = matchAll(MODAL[k], p);
  return { spans, idents, nums, quoted, neg, cond, modal };
}

// ---------------------------------------------------------------------------
// 段落の対応づけ(単調な対応。1:1・分割 1:2/1:3・統合 2:1/3:1・2:2・削除・追加)
//   類似度は文字 2-gram 集合の Jaccard 係数。計算量を抑えるため帯状の範囲だけを探す。
// ---------------------------------------------------------------------------
function bigrams(s) {
  const t = s.replace(/[\s#>*_`|\-、。，．,.（）()「」『』[\]:：]/g, '');
  const set = new Set();
  for (let i = 0; i + 1 < t.length; i++) set.add(t.slice(i, i + 2));
  if (t.length === 1) set.add(t);
  return set;
}
function jaccard(a, b) {
  if (a.size === 0 && b.size === 0) return 1;
  let inter = 0;
  const [s, l] = a.size <= b.size ? [a, b] : [b, a];
  for (const x of s) if (l.has(x)) inter++;
  return inter / (a.size + b.size - inter);
}
function rangeSets(units) {
  // memo[k][i] = 2-gram set of units i..i+k-1 (k = 1..3)
  const memo = [null, units.map((u) => u.grams), [], []];
  for (const k of [2, 3]) {
    for (let i = 0; i + k <= units.length; i++) {
      const s = new Set(memo[k - 1][i]);
      for (const x of units[i + k - 1].grams) s.add(x);
      memo[k][i] = s;
    }
  }
  return memo;
}

const STEPS = [[1, 1], [1, 2], [2, 1], [1, 3], [3, 1], [2, 2], [1, 0], [0, 1]];
const GAP = 0.8;

function align(bu, au) {
  const n = bu.length, m = au.length;
  const bs = rangeSets(bu), as = rangeSets(au);
  // 帯の中心は段落数の比で補正しているので、幅は小さくてよい。差の全量を足すと大きな文書で計算量が膨らむ
  const band = 30 + Math.ceil(Math.abs(n - m) / 8);
  const INF = 1e9;
  const D = Array.from({ length: n + 1 }, () => new Float64Array(m + 1).fill(INF));
  const P = Array.from({ length: n + 1 }, () => new Int8Array(m + 1).fill(-1));
  D[0][0] = 0;
  for (let i = 0; i <= n; i++) {
    const center = n === 0 ? 0 : Math.round((i * m) / n);
    const lo = Math.max(0, center - band), hi = Math.min(m, center + band);
    for (let j = lo; j <= hi; j++) {
      if (i === 0 && j === 0) continue;
      let best = INF, bk = -1;
      for (let k = 0; k < STEPS.length; k++) {
        const [di, dj] = STEPS[k];
        if (i - di < 0 || j - dj < 0) continue;
        const prev = D[i - di][j - dj];
        if (prev >= INF) continue;
        let c;
        if (di === 0 || dj === 0) c = GAP * (di + dj);
        // まとめた段落の数で重みを付ける(重みなしだと、まとめるほどコストの項が減って 2:2 などが不当に有利になる)
        else c = ((di + dj) / 2) * (1 - jaccard(bs[di][i - di], as[dj][j - dj])) + 0.05 * (di + dj - 2);
        if (prev + c < best) { best = prev + c; bk = k; }
      }
      D[i][j] = best; P[i][j] = bk;
    }
  }
  const pairs = [];
  let i = n, j = m;
  while (i > 0 || j > 0) {
    const k = P[i][j];
    if (k < 0) { // 帯の外に出た場合の保険(通常は起きない)
      pairs.push({ b: [...Array(i).keys()], a: [...Array(j).keys()] }); break;
    }
    const [di, dj] = STEPS[k];
    pairs.push({ b: Array.from({ length: di }, (_, x) => i - di + x), a: Array.from({ length: dj }, (_, x) => j - dj + x) });
    i -= di; j -= dj;
  }
  return pairs.reverse();
}

// ---------------------------------------------------------------------------
// 比較
// ---------------------------------------------------------------------------
const hasJapanese = (s) => /[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}]/u.test(s);
const sum = (arr, f) => arr.reduce((x, y) => x + f(y), 0);
const flat = (arr, f) => arr.flatMap(f);

function prepare(text) {
  const { lines, blocks } = splitBlocks(text);
  const prose = [], prot = [];
  for (const b of blocks) {
    if (b.kind === 'prose') { const info = analyzeProse(b.text); prose.push({ ...b, ...info, grams: bigrams(b.text) }); }
    else prot.push(b);
  }
  return { lines, prose, prot };
}

function lineRange(units, idx) {
  if (idx.length === 0) return null;
  return [units[idx[0]].start + 1, units[idx[idx.length - 1]].end + 1];
}
const fmtRange = (r) => (r ? (r[0] === r[1] ? `L${r[0]}` : `L${r[0]}-${r[1]}`) : '-');

function compare(B, A) {
  const findings = [];
  const add = (f) => { f.id = `F${findings.length + 1}`; findings.push(f); return f; };
  const pairs = align(B.prose, A.prose);
  const pairOfBefore = new Map(), pairOfAfter = new Map();
  pairs.forEach((p, k) => { p.b.forEach((i) => pairOfBefore.set(i, k)); p.a.forEach((j) => pairOfAfter.set(j, k)); });

  // --- 段落ごとの比較(否定・条件・確度) ---
  pairs.forEach((p, k) => {
    const bl = lineRange(B.prose, p.b), al = lineRange(A.prose, p.a);
    const bU = p.b.map((i) => B.prose[i]), aU = p.a.map((j) => A.prose[j]);
    if (p.a.length === 0) {
      add({ severity: 'info', category: 'DEL', pairs: [k], before_lines: bl, after_lines: null,
        message: '段落が削除された。情報量のない反復だったかを確かめる',
        excerpt: bU.map((u) => u.text).join(' ').slice(0, 60) });
      return;
    }
    if (p.b.length === 0) {
      add({ severity: 'info', category: 'ADD', pairs: [k], before_lines: null, after_lines: al,
        message: '原文にない段落が追加された。新しい情報を足していないかを確かめる',
        excerpt: aU.map((u) => u.text).join(' ').slice(0, 60) });
      return;
    }
    const nb = sum(bU, (u) => u.neg.length), na = sum(aU, (u) => u.neg.length);
    const d = na - nb;
    if (Math.abs(d) % 2 === 1) {
      add({ severity: 'risk', category: 'NEG', pairs: [k], before_lines: bl, after_lines: al,
        message: `否定の数が奇数だけ変わった(前 ${nb} → 後 ${na})。論理が反転していないかを確かめる`,
        before_markers: flat(bU, (u) => u.neg), after_markers: flat(aU, (u) => u.neg) });
    } else if (d < 0) {
      add({ severity: 'info', category: 'NEG', pairs: [k], before_lines: bl, after_lines: al,
        message: `否定が ${-d} 個減った(偶数)。二重否定の畳み込みとみなした`,
        before_markers: flat(bU, (u) => u.neg), after_markers: flat(aU, (u) => u.neg) });
    }
    for (const [group, cat] of [[COND, 'C'], [MODAL, 'M']]) {
      for (const cls of Object.keys(group)) {
        const xb = flat(bU, (u) => (cat === 'C' ? u.cond : u.modal)[cls]);
        const xa = flat(aU, (u) => (cat === 'C' ? u.cond : u.modal)[cls]);
        if (xa.length < xb.length) {
          add({ severity: 'risk', category: cat, cls, pairs: [k], before_lines: bl, after_lines: al,
            message: `${CLASS_LABEL[cls]}の印が減った(前 ${xb.length} → 後 ${xa.length})`,
            before_markers: xb, after_markers: xa });
        }
      }
    }
  });

  // --- 文書全体での比較(数値・識別子・「」の語)。段落の削除や移動では誤検出しない ---
  const docTokens = (D, key) => {
    const map = new Map();
    D.prose.forEach((u, i) => u[key].forEach((t) => { if (!map.has(t)) map.set(t, i); }));
    return map;
  };
  for (const [key, cat, label, addedSeverity] of [['nums', 'N', '数値', 'risk'], ['idents', 'I', '識別子', 'risk'], ['quoted', 'I', '「」の語', 'info']]) {
    const tb = docTokens(B, key), ta = docTokens(A, key);
    for (const [t, i] of tb) {
      if (!ta.has(t)) {
        add({ severity: 'risk', category: cat, pairs: [pairOfBefore.get(i)], before_lines: lineRange(B.prose, [i]), after_lines: null,
          message: `${label}「${t}」が書き換え後の本文から消えた`, token: t });
      }
    }
    for (const [t, j] of ta) {
      if (tb.has(t)) continue;
      const k = pairOfAfter.get(j);
      // 列挙を箇条書きに開いて「次の 4 つ」と書いた場合は、新しい事実ではなく項目数なので情報扱いにする
      const count = key === 'nums' && /^\d+つ?$/.test(t) && k !== undefined
        ? (pairs[k].a.map((x) => A.prose[x].text).join('\n').match(LIST_ITEM) || []).length : -1;
      if (count === parseInt(t, 10)) {
        add({ severity: 'info', category: cat, pairs: [k], before_lines: null, after_lines: lineRange(A.prose, [j]),
          message: `${label}「${t}」が現れたが、同じ段落の箇条書きの項目数と一致するため項目数とみなした`, token: t });
        continue;
      }
      add({ severity: addedSeverity, category: cat, pairs: [k], before_lines: null, after_lines: lineRange(A.prose, [j]),
        message: `${label}「${t}」が書き換え後に現れた(原文にない)`, token: t });
    }
  }

  // --- 保護領域(コード・引用・数式・URL など)は 1 文字でも違えば恐れあり ---
  const norm = (s) => s.replace(/[ \t]+$/gm, '');
  const pb = B.prot.map((b) => norm(b.text)), pa = A.prot.map((b) => norm(b.text));
  if (pb.length === pa.length) {
    pb.forEach((t, i) => {
      if (t !== pa[i]) {
        add({ severity: 'risk', category: 'P', prot: i, before_lines: [B.prot[i].start + 1, B.prot[i].end + 1], after_lines: [A.prot[i].start + 1, A.prot[i].end + 1],
          message: 'コード・引用・数式などの保護領域が変わった', excerpt: t.slice(0, 60) });
      }
    });
  } else {
    add({ severity: 'risk', category: 'P', prot: null, before_lines: null, after_lines: null, unrevertable: true,
      message: `保護領域の数が変わった(前 ${pb.length} → 後 ${pa.length})。自動では戻せない` });
  }
  const spanCount = (D) => {
    const m = new Map();
    D.prose.forEach((u, i) => u.spans.forEach((s) => m.set(s, (m.get(s) || []).concat(i))));
    return m;
  };
  const sb = spanCount(B), sa = spanCount(A);
  // 消えた・変わったインライン要素は、対応づけた段落ごとに数を比べて特定する。
  // 文書全体の数だけで比べると、同じ要素が複数回出るときに無関係な段落を指してしまうため
  pairs.forEach((p, k) => {
    const cnt = (units, D) => { const m = new Map(); units.forEach((x) => D.prose[x].spans.forEach((s) => m.set(s, (m.get(s) || 0) + 1))); return m; };
    const cb = cnt(p.b, B), ca = cnt(p.a, A);
    for (const [s, c] of cb) {
      if ((ca.get(s) || 0) < c) {
        add({ severity: 'risk', category: 'P', pairs: [k], before_lines: lineRange(B.prose, p.b), after_lines: lineRange(A.prose, p.a),
          message: `インラインのコード・数式・URL「${s.slice(0, 40)}」が消えたか変わった`, token: s });
      }
    }
  });
  for (const [s, idx] of sa) {
    if (!sb.has(s)) {
      const j = idx[0];
      add({ severity: 'risk', category: 'P', pairs: [pairOfAfter.get(j)], before_lines: null, after_lines: lineRange(A.prose, [j]),
        message: `インラインのコード・数式・URL「${s.slice(0, 40)}」が書き換え後に現れた`, token: s });
    }
  }

  // 表示用の行範囲を対応する段落で補う
  for (const f of findings) {
    if (f.pairs && f.pairs.length === 1 && f.pairs[0] !== undefined) {
      const p = pairs[f.pairs[0]];
      f.before_lines = f.before_lines || lineRange(B.prose, p.b);
      f.after_lines = f.after_lines || lineRange(A.prose, p.a);
    }
  }
  return { findings, pairs };
}

// ---------------------------------------------------------------------------
// 恐れありの段落を原文に戻す
// ---------------------------------------------------------------------------
function revert(B, A, pairs, findings, keep) {
  const target = new Set(), protTarget = new Set();
  const unrevertable = [];
  for (const f of findings) {
    if (f.severity !== 'risk' || keep.has(f.id)) continue;
    if (f.unrevertable) { unrevertable.push(f.id); continue; }
    if (f.category === 'P' && f.prot !== undefined && f.prot !== null) { protTarget.add(f.prot); continue; }
    (f.pairs || []).forEach((k) => { if (k !== undefined) target.add(k); });
  }
  // 置き換え表: 書き換え後の行番号 → 置き換える行
  const replace = new Map(); // startLine -> { end, lines }
  const insertAfter = new Map(); // afterLine(-1 = 先頭) -> lines[]
  for (const k of target) {
    const p = pairs[k];
    const bLines = p.b.length ? B.lines.slice(B.prose[p.b[0]].start, B.prose[p.b[p.b.length - 1]].end + 1) : [];
    if (p.a.length) {
      const s = A.prose[p.a[0]].start, e = A.prose[p.a[p.a.length - 1]].end;
      replace.set(s, { end: e, lines: bLines });
    } else {
      // 削除された段落を戻す: 直前の対応段落の後ろに差し込む
      let anchor = -1;
      for (let q = k - 1; q >= 0; q--) if (pairs[q].a.length) { anchor = A.prose[pairs[q].a[pairs[q].a.length - 1]].end; break; }
      insertAfter.set(anchor, (insertAfter.get(anchor) || []).concat(['', ...bLines]));
    }
  }
  for (const i of protTarget) {
    replace.set(A.prot[i].start, { end: A.prot[i].end, lines: B.lines.slice(B.prot[i].start, B.prot[i].end + 1) });
  }
  const out = [];
  if (insertAfter.has(-1)) out.push(...insertAfter.get(-1).slice(1), '');
  for (let i = 0; i < A.lines.length; i++) {
    const r = replace.get(i);
    if (r) { out.push(...r.lines); i = r.end; }
    else out.push(A.lines[i]);
    if (insertAfter.has(i)) out.push(...insertAfter.get(i));
  }
  return { text: out.join('\n'), reverted: findings.filter((f) => f.severity === 'risk' && !keep.has(f.id) && !f.unrevertable).map((f) => f.id), unrevertable };
}

// ---------------------------------------------------------------------------
// 出力
// ---------------------------------------------------------------------------
function report(findings) {
  const risk = findings.filter((f) => f.severity === 'risk'), info = findings.filter((f) => f.severity === 'info');
  const out = [`意味の検算: 恐れあり ${risk.length} 件 / 情報 ${info.length} 件`];
  for (const f of [...risk, ...info]) {
    out.push(`[${f.id}] ${f.severity === 'risk' ? '恐れあり' : '情報'} ${f.category} 前 ${fmtRange(f.before_lines)} / 後 ${fmtRange(f.after_lines)}: ${f.message}`);
    if (f.before_markers) out.push(`      前の印: ${f.before_markers.join('、') || '(なし)'}`);
    if (f.after_markers) out.push(`      後の印: ${f.after_markers.join('、') || '(なし)'}`);
    if (f.excerpt) out.push(`      抜粋: ${f.excerpt}`);
  }
  out.push('判定していないもの: 意味が保たれたか(この検査は印の数を比べるだけで、何も出ないことは合格を意味しない)');
  return out.join('\n');
}

function main() {
  const args = parseArgs(process.argv);
  if (!args) {
    console.error('使い方: meiseki-invariants.js --before 前.md --after 後.md [--json] [--revert-risky --out 最終.md [--keep F1,F2]]');
    return 2;
  }
  let bt, at;
  try { bt = fs.readFileSync(args.before, 'utf8'); at = fs.readFileSync(args.after, 'utf8'); }
  catch (e) { console.error(`読み込めません: ${e.message}`); return 2; }
  if (!hasJapanese(bt)) return 3;
  const B = prepare(bt), A = prepare(at);
  const { findings, pairs } = compare(B, A);
  const risk = findings.filter((f) => f.severity === 'risk');

  if (args.revert) {
    const r = revert(B, A, pairs, findings, args.keep);
    fs.writeFileSync(args.out, r.text);
    const msg = { reverted: r.reverted, kept: [...args.keep], unrevertable: r.unrevertable };
    if (args.json) process.stdout.write(JSON.stringify({ findings, ...msg, not_judged: ['meaning_preservation'] }, null, 2) + '\n');
    else process.stdout.write(`${report(findings)}\n原文に戻した指摘: ${r.reverted.join(', ') || '(なし)'} / 戻さなかった指摘: ${[...args.keep].join(', ') || '(なし)'} / 自動で戻せない指摘: ${r.unrevertable.join(', ') || '(なし)'}\n`);
    return r.unrevertable.length ? 1 : 0;
  }
  if (args.json) {
    process.stdout.write(JSON.stringify({ summary: { risk: risk.length, info: findings.length - risk.length }, findings, not_judged: ['meaning_preservation'] }, null, 2) + '\n');
  } else {
    process.stdout.write(report(findings) + '\n');
  }
  return risk.length ? 1 : 0;
}

if (require.main === module) process.exitCode = main();
module.exports = { main, splitBlocks, analyzeProse, align, prepare, compare, revert };

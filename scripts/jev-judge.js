#!/usr/bin/env node
// jev-judge.js — Jev(TypeSafe AI)への共通クライアント(依存ゼロ・Node 18+)
//
// meiseki / yorisoi の任意判定層。キーが無い環境では exit 3 で静かに退き、
// 呼び出し側(スキル層)は従来の方法へフォールバックする。hook からは使わない。
//
// 使い方:
//   echo '{"state":"...","questions":{...}}' | node scripts/jev-judge.js
//   node scripts/jev-judge.js --check    # キーの有無と疎通を確認
//   node scripts/jev-judge.js --setup    # キーを対話で保存(~/.config/meiseki/jev.key)
//
// 終了コード:
//   0 = 判定取得(stdout に結果 JSON)
//   2 = API 失敗・タイムアウト(呼び出し側はフォールバック)
//   3 = キー未設定(呼び出し側はスキップ)
//
// 無効化(データを外部 API に送りたくない場合):
//   - 環境変数 MEISEKI_JEV_DISABLE=1
//   - 作業ディレクトリまたはその祖先に .meiseki-no-jev ファイルを置く(空で可)
//   どちらも exit 3(キー未設定と同じ)になり、呼び出し側は従来動作へフォールバックする。
//   判定対象のテキストが TypeSafe のサーバーへ送信されるため、標準アカウント(非 ZDR)では
//   運用・不正利用防止目的で一定期間保持されうる。機密文書を扱うディレクトリでは
//   .meiseki-no-jev を置くこと。
// キーの解決順: $TYPESAFE_API_KEY → $TYPESAFE_JEV_KEY_CMD → ~/.config/meiseki/jev.cmd(取得コマンド) → ~/.config/meiseki/jev.key
//   1Password CLI の例: export TYPESAFE_JEV_KEY_CMD='op read "op://Private/TypeSafe Jev/credential"'
//   (キーがディスクにもシェル履歴にも残らないため、シークレットマネージャ利用時はこれを推奨)
// エンドポイント/モデルの差し替え: $TYPESAFE_JEV_ENDPOINT / $TYPESAFE_JEV_MODEL
// キーをログ・stdout・エラーメッセージへ出さないこと。

'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const ENDPOINT = process.env.TYPESAFE_JEV_ENDPOINT || 'https://api.typesafe.ai/v1/systemone';
const MODEL = process.env.TYPESAFE_JEV_MODEL || 'jev-latest';
const KEY_FILE = path.join(os.homedir(), '.config', 'meiseki', 'jev.key');
const CMD_FILE = path.join(os.homedir(), '.config', 'meiseki', 'jev.cmd');
const TIMEOUT_MS = Number(process.env.TYPESAFE_JEV_TIMEOUT_MS || 10000);

// ポリシー設定: プロジェクトの .meiseki.json(cwd から祖先探索)または
// ~/.config/meiseki/config.json の "jev" キーで、スコープごとに allow / ask / deny を指定できる。
//   { "jev": "deny" }                                  … 全スコープ拒否
//   { "jev": { "meiseki": "allow", "yorisoi": "ask" } } … スコープ別
// 既定は meiseki=allow(キー設定を同意とみなす)、yorisoi=ask(全文相当を送るため)。
// "ask" のスコープは、スキル層がユーザーに確認して --consented を付けたときだけ実行される。
const POLICY_DEFAULT = { meiseki: 'allow', yorisoi: 'ask' };

function loadJevPolicy(scope) {
  function readJson(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (_) { return null; } }
  function pick(cfg) {
    if (!cfg || typeof cfg.jev === 'undefined') return null;
    if (typeof cfg.jev === 'string') return { value: cfg.jev };
    if (cfg.jev && typeof cfg.jev === 'object' && typeof cfg.jev[scope] === 'string') return { value: cfg.jev[scope] };
    return null;
  }
  let dir = process.cwd();
  for (;;) {
    const hit = pick(readJson(path.join(dir, '.meiseki.json')));
    if (hit) return { ...hit, source: path.join(dir, '.meiseki.json') };
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  const g = pick(readJson(path.join(os.homedir(), '.config', 'meiseki', 'config.json')));
  if (g) return { ...g, source: '~/.config/meiseki/config.json' };
  return { value: POLICY_DEFAULT[scope] || 'allow', source: '(既定値)' };
}

// ディレクトリ単位の無効化: cwd から / まで .meiseki-no-jev を探す。
// 見つけたらそのパスを返す(呼び出し側は Jev 層をスキップする)。
function findNoJevMarker() {
  if (process.env.MEISEKI_JEV_DISABLE === '1') return '(環境変数 MEISEKI_JEV_DISABLE=1)';
  let dir = process.cwd();
  for (;;) {
    const marker = path.join(dir, '.meiseki-no-jev');
    try { fs.statSync(marker); return marker; } catch (_) {}
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

// キーコマンド(op read 等)の結果を OS のセキュアストアにキャッシュする。
// 1Password 等の承認プロンプトが呼び出しごとに出るのを防ぐため。キーは OS の
// 暗号化ストアに入り、平文ファイルには書かない。TTL 既定 1 時間。
//   macOS: キーチェーン(security) / Linux: libsecret(secret-tool) / Windows: DPAPI
// 期限切れのエントリは次回アクセス時に削除される(遅延削除)。
// TYPESAFE_JEV_KEY_TTL=0 で無効化、`--clear-cache` で即時削除できる。
const CACHE_SERVICE = 'meiseki-jev-cache';
const CACHE_TTL = Number(process.env.TYPESAFE_JEV_KEY_TTL ?? 3600);

function hasCmd(name) {
  try { require('child_process').execSync(`command -v ${name}`, { stdio: 'ignore', shell: '/bin/sh' }); return true; } catch (_) { return false; }
}

function cacheBackend() {
  if (CACHE_TTL <= 0) return null;
  const { execFileSync } = require('child_process');
  const user = os.userInfo().username;
  if (process.platform === 'darwin' && hasCmd('security')) {
    // デフォルトキーチェーンが未設定の Mac では、書き込み時に GUI ダイアログ
    // (「保存するキーチェーンが見つかりません」)が出てしまう。バックグラウンドの
    // スクリプトがダイアログを出すのは避けたいので、その場合はキャッシュしない。
    try {
      execFileSync('security', ['default-keychain', '-d', 'user'], { stdio: 'ignore' });
    } catch (_) { return null; }
    return {
      name: 'keychain',
      get() { try { return execFileSync('security', ['find-generic-password', '-s', CACHE_SERVICE, '-a', user, '-w'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch (_) { return null; } },
      set(v) { try { execFileSync('security', ['add-generic-password', '-U', '-s', CACHE_SERVICE, '-a', user, '-w', v], { stdio: 'ignore' }); } catch (_) {} },
      clear() { try { execFileSync('security', ['delete-generic-password', '-s', CACHE_SERVICE, '-a', user], { stdio: 'ignore' }); return true; } catch (_) { return false; } },
    };
  }
  if (process.platform === 'linux' && hasCmd('secret-tool')) {
    return {
      name: 'libsecret',
      get() { try { return execFileSync('secret-tool', ['lookup', 'service', CACHE_SERVICE, 'account', user], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch (_) { return null; } },
      set(v) { try { execFileSync('secret-tool', ['store', `--label=${CACHE_SERVICE}`, 'service', CACHE_SERVICE, 'account', user], { input: v, stdio: ['pipe', 'ignore', 'ignore'] }); } catch (_) {} },
      clear() { try { execFileSync('secret-tool', ['clear', 'service', CACHE_SERVICE, 'account', user], { stdio: 'ignore' }); return true; } catch (_) { return false; } },
    };
  }
  if (process.platform === 'win32') {
    const file = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'meiseki', 'jev.cache');
    const ps = (script, env) => execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', script], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], env: { ...process.env, ...env } }).trim();
    return {
      name: 'dpapi',
      get() {
        try {
          return ps(`Add-Type -AssemblyName System.Security; $b=[Convert]::FromBase64String((Get-Content -Raw $env:MEISEKI_CACHE_FILE)); [Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect($b,$null,'CurrentUser'))`, { MEISEKI_CACHE_FILE: file });
        } catch (_) { return null; }
      },
      set(v) {
        try {
          fs.mkdirSync(path.dirname(file), { recursive: true });
          ps(`Add-Type -AssemblyName System.Security; $b=[Security.Cryptography.ProtectedData]::Protect([Text.Encoding]::UTF8.GetBytes($env:MEISEKI_CACHE_VAL),$null,'CurrentUser'); Set-Content -Path $env:MEISEKI_CACHE_FILE -Value ([Convert]::ToBase64String($b))`, { MEISEKI_CACHE_VAL: v, MEISEKI_CACHE_FILE: file });
        } catch (_) {}
      },
      clear() { try { fs.unlinkSync(file); return true; } catch (_) { return false; } },
    };
  }
  return null; // バックエンドなし(ヘッドレス Linux 等)はキャッシュせず毎回取得する
}

function cacheGetFresh(backend) {
  const v = backend.get();
  if (!v) return null;
  const i = v.indexOf(':');
  if (i < 0) { backend.clear(); return null; }
  const age = Date.now() / 1000 - Number(v.slice(0, i));
  if (!(age >= 0 && age < CACHE_TTL)) { backend.clear(); return null; } // 期限切れは実削除
  return v.slice(i + 1) || null;
}

function keychainClear() {
  const b = cacheBackend();
  return b ? b.clear() : false;
}

function runKeyCmd(cmd, label) {
  const backend = cacheBackend();
  if (backend) {
    const hit = cacheGetFresh(backend);
    if (hit) return hit;
  }
  try {
    const { execSync } = require('child_process');
    const k = execSync(cmd, { encoding: 'utf8', timeout: 15000, stdio: ['ignore', 'pipe', 'pipe'] }).trim();
    if (k) {
      if (backend) {
        backend.set(`${Math.floor(Date.now() / 1000)}:${k}`);
        // 書き込みを読み戻して検証する。黙って失敗すると、次回また承認プロンプトが
        // 出て「キャッシュが効いていない」ように見えるため、失敗は警告として出す。
        if (cacheGetFresh(backend) !== k) {
          console.error(`キーのキャッシュ保存に失敗しました(${backend.name})。次回も取得コマンドが実行されます。`);
        }
      }
      return k;
    }
    console.error(`${label} の出力が空でした。`);
  } catch (_) {
    console.error(`${label} の実行に失敗しました(シークレットマネージャに未ログインの可能性)。`);
  }
  return null;
}

// 起動ごとに 1 回、期限切れキャッシュを掃除する。キーの解決経路に関係なく呼ぶことで、
// キーコマンドを使わなくなった環境に残った古いエントリも次の起動で消える。
let purgedThisRun = false;
function purgeStaleCache() {
  if (purgedThisRun) return;
  purgedThisRun = true;
  const backend = cacheBackend();
  if (backend) { try { cacheGetFresh(backend); } catch (_) { /* 掃除失敗は無視 */ } }
}

function resolveKey() {
  purgeStaleCache();
  const env = (process.env.TYPESAFE_API_KEY || '').trim();
  if (env) return env;
  // シークレットマネージャ連携: 指定コマンドの stdout をキーとして使う。
  // コマンド失敗(未ログイン等)はキー未設定と同じ扱いにし、理由だけ stderr へ出す。
  const cmd = (process.env.TYPESAFE_JEV_KEY_CMD || '').trim();
  if (cmd) {
    return runKeyCmd(cmd, 'TYPESAFE_JEV_KEY_CMD'); // コマンド指定時はファイルへフォールバックしない
  }
  // コマンドファイル(~/.config/meiseki/jev.cmd): jev:setup に op:// 参照や cmd: を
  // 渡したときに作られる。保存されているのは取得コマンドの文字列だけで、キー本体は
  // 毎回シークレットマネージャから取得する(ディスクに残らない)。
  try {
    const fileCmd = fs.readFileSync(CMD_FILE, 'utf8').trim();
    if (fileCmd) {
      return runKeyCmd(fileCmd, 'jev.cmd'); // コマンドファイルがある場合もキーファイルへはフォールバックしない
    }
  } catch (_) { /* コマンドファイルなしは次へ */ }
  try {
    const k = fs.readFileSync(KEY_FILE, 'utf8').trim();
    if (k) return k;
  } catch (_) { /* ファイルなしはキー未設定として扱う */ }
  return null;
}

async function callJev(key, state, questions) {
  const started = Date.now();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(ENDPOINT, {
      method: 'POST',
      signal: ctrl.signal,
      headers: {
        'Authorization': `Bearer ${key}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ model: MODEL, state, questions }),
    });
    const elapsed_ms = Date.now() - started;
    if (!res.ok) {
      // 429/529 は本来バックオフ対象だが、対話フローを待たせないため 1 回で諦めて
      // フォールバックに回す(高速化層が遅延源になるのを避ける)
      return { ok: false, status: res.status, elapsed_ms };
    }
    const body = await res.json();
    return { ok: true, body, elapsed_ms };
  } catch (e) {
    return { ok: false, status: 0, error: e.name === 'AbortError' ? 'timeout' : 'network', elapsed_ms: Date.now() - started };
  } finally {
    clearTimeout(timer);
  }
}

async function readStdin() {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
}

async function cmdSetup() {
  // キーを対話で受け取り、エコーせずに保存する。疎通確認まで行う。
  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin, output: process.stderr, terminal: true });
  // 入力エコー抑止(端末のときだけ)
  const muted = process.stdin.isTTY;
  if (muted) {
    const origWrite = rl._writeToOutput.bind(rl);
    rl._writeToOutput = (s) => { if (s.includes('API key')) origWrite(s); };
  }
  const key = await new Promise((resolve) => rl.question('TypeSafe API key / 1Password 秘密参照(op://...) (入力は表示されません): ', (a) => { rl.close(); resolve(a.trim()); }));
  process.stderr.write('\n');
  if (!key) { console.error('入力が空です。中止しました。'); return 3; }
  fs.mkdirSync(path.dirname(KEY_FILE), { recursive: true, mode: 0o700 });

  // 1Password の秘密参照(op://...)または cmd: 接頭辞: キー本体ではなく
  // 「取得コマンド」を保存する。キーはディスクに残らない。
  if (key.startsWith('op://') || key.startsWith('cmd:')) {
    const cmd = key.startsWith('op://') ? `op read ${JSON.stringify(key)}` : key.slice(4).trim();
    fs.writeFileSync(CMD_FILE, cmd + '\n', { mode: 0o600 });
    console.error(`取得コマンドを保存しました: ${CMD_FILE}(キー本体はディスクに残りません)`);
    try { fs.unlinkSync(KEY_FILE); console.error(`旧キーファイルを削除しました: ${KEY_FILE}`); } catch (_) {}
    const k = resolveKey();
    if (!k) { console.error('取得コマンドの実行に失敗しました。1Password なら `op signin` 済みか、参照パスが正しいかを確認してください。'); return 2; }
    const probe = await callJev(k, 'ping', { alive: { type: 'noul', instructions: 'Is this a ping?' } });
    if (probe.ok) { console.error(`疎通 OK (${probe.elapsed_ms}ms, model: ${probe.body.model || MODEL})`); return 0; }
    console.error(`取得はできましたが疎通に失敗しました(status=${probe.status}${probe.error ? ', ' + probe.error : ''})。`);
    return 2;
  }

  fs.writeFileSync(KEY_FILE, key + '\n', { mode: 0o600 });
  console.error(`保存しました: ${KEY_FILE} (0600)`);
  const probe = await callJev(key, 'ping', { alive: { type: 'noul', instructions: 'Is this a ping?' } });
  if (probe.ok) { console.error(`疎通 OK (${probe.elapsed_ms}ms, model: ${probe.body.model || MODEL})`); return 0; }
  console.error(`保存はしましたが疎通に失敗しました(status=${probe.status}${probe.error ? ', ' + probe.error : ''})。キーの値とネットワークを確認してください。`);
  return 2;
}

async function cmdCheck() {
  const marker = findNoJevMarker();
  if (marker) { console.error(`このディレクトリでは Jev が無効化されています: ${marker}。判定は行われず、従来動作になります。`); return 3; }
  const key = resolveKey();
  if (!key) { console.error('キー未設定(TYPESAFE_API_KEY / TYPESAFE_JEV_KEY_CMD / ~/.config/meiseki/jev.key)。Jev 層はスキップされ、従来動作になります。'); return 3; }
  const probe = await callJev(key, 'ping', { alive: { type: 'noul', instructions: 'Is this a ping?' } });
  if (probe.ok) { console.error(`疎通 OK (${probe.elapsed_ms}ms, model: ${probe.body.model || MODEL})`); return 0; }
  console.error(`キーはありますが疎通に失敗しました(status=${probe.status}${probe.error ? ', ' + probe.error : ''})。`);
  return 2;
}

async function cmdJudge() {
  const marker = findNoJevMarker();
  if (marker) { console.error(`Jev 無効化(${marker})。テキストは送信されません。`); return 3; }
  const key = resolveKey();
  if (!key) return 3;
  let input;
  try {
    input = JSON.parse(await readStdin());
  } catch (_) {
    console.error('stdin が JSON として読めません({state, questions} を渡してください)。');
    return 2;
  }
  if (!input || typeof input.state === 'undefined' || !input.questions) {
    console.error('state と questions が必要です。');
    return 2;
  }
  const r = await callJev(key, input.state, input.questions);
  if (!r.ok) {
    console.error(`Jev 呼び出し失敗(status=${r.status}${r.error ? ', ' + r.error : ''}, ${r.elapsed_ms}ms)。フォールバックしてください。`);
    return 2;
  }
  const n = Object.keys(input.questions).length;
  process.stdout.write(JSON.stringify({ ...r.body, _meta: { elapsed_ms: r.elapsed_ms, questions: n, endpoint_default: !process.env.TYPESAFE_JEV_ENDPOINT } }) + '\n');
  return 0;
}

(async () => {
  const argv = process.argv.slice(2);
  const has = (f) => argv.includes(f);
  const scopeIdx = argv.indexOf('--scope');
  const scope = scopeIdx >= 0 ? (argv[scopeIdx + 1] || 'meiseki') : 'meiseki';
  let code;
  if (has('--clear-cache')) { code = keychainClear() ? (console.error('キーチェーンのキャッシュを削除しました。'), 0) : (console.error('キャッシュはありません。'), 0); }
  else if (has('--setup')) code = await cmdSetup();
  else if (has('--check')) code = await cmdCheck();
  else if (has('--policy')) {
    const marker = findNoJevMarker();
    const p = loadJevPolicy(scope);
    process.stdout.write(JSON.stringify({ scope, policy: marker ? 'deny' : p.value, source: marker ? String(marker) : p.source, key_configured: !!resolveKey() }) + '\n');
    code = 0;
  } else {
    const p = loadJevPolicy(scope);
    if (p.value === 'deny') {
      console.error(`Jev はポリシーで拒否されています(scope=${scope}, ${p.source})。テキストは送信されません。`);
      code = 3;
    } else if (p.value === 'ask' && !has('--consented')) {
      console.error(`Jev の実行には確認が必要です(scope=${scope}, policy=ask, ${p.source})。ユーザーの同意を得てから --consented を付けて再実行してください。送信は行っていません。`);
      code = 3;
    } else {
      code = await cmdJudge();
    }
  }
  process.exit(code);
})();

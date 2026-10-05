# 絵解きノート（explainer.html）の書き方

## 1. 役割

絵解きノートは、その話題を知らない人が絵とひとことで直感をつかむためのページである。大きな絵を先に見せ、言葉は少なくする。細かい定義や数式はテキストブックが受け持つので、ここには持ち込まない。

資料 1 つにつき 1 ファイルで、セッションのたびに study.md に合わせて書き足す（§7）。置き場所は `.rikai/<資料名>.explainer.html` である。単体で開けるファイルにし、外部のフォント・スクリプト・スタイルシート・画像を読み込まない。外部サービスへの公開もしない。

eli5 スキルが使える環境では、その流儀（大きな絵、少ない言葉）を取り入れる。使えない環境でも、この指針だけで書ける。

## 2. ファイルの作り方

初回は `assets/explainer-template.html` を `.rikai/<資料名>.explainer.html` として複製し、次の 2 つを置き換える。

| 置き換え箇所 | 入れるもの |
|---|---|
| `{{SOURCE_NAME}}`（3 か所） | 資料のファイル名。`<` と `&` は `&lt;` `&amp;` にする |
| `{{UPDATED}}` | 更新日（例 `2026年10月4日`） |

2 回目以降は既存のファイルを直接編集する。更新日を書き換え、進捗を書き直し、論点を書き足す。`<style>` の中は変更しない。

雛形の文言は日本語である。日本語以外の言語で書くときは、§9 に従って雛形の固定の文言も訳す。

## 3. 進捗

`<!-- rikai:progress:start -->` と `<!-- rikai:progress:end -->` の間を、毎回まるごと書き直す。分子はこのノートに載せた論点の数（挑戦済みで、状態が `復習中` か `卒業` の論点）、分母は状態が `要再抽出` の論点を除いた全論点の数である。`要再抽出` の論点は、書きもせず数えもしない。2 つ目の段落には、復習中の論点へのリンクを示す。復習中の論点がなければ、2 つ目の段落を「復習中の論点はありません。」にする。

```html
<div class="score">
  <p class="num"><b>17</b><span>/ 26 論点に挑戦済み</span></p>
  <p class="legend">復習中：<a href="#topic-012">調査 5 種類の厳格さ</a>、<a href="#topic-014">ベースラインは最低ライン</a></p>
</div>
```

## 4. 論点 1 つ

論点は `<!-- rikai:topics:start -->` と `<!-- rikai:topics:end -->` の間に、資料に出てくる順で並べる。順はアンカーの `line` の昇順で決め、`line` が `null` の論点は、原文での見出しの順（`heading_path` の見出しが原文に出てくる位置）で決める。1 論点は `article` 要素 1 つで、`id` に論点 id を入れる。論点 id は `id` 属性とリンク先にだけ使い、読者に見える文字としては書かない。

```html
<article class="q" id="topic-016">
  <div class="qhead"><span class="qno">1.7 事業継続</span><span class="chip ng">復習中</span></div>
  <h2>RPO はどの区間？</h2>
  <figure class="pic">
    <svg viewBox="0 0 480 185" role="img" aria-label="時間の線の上に、左からセーブと停電の印。セーブから停電までの区間が RPO">
      <rect x="60" y="74" width="160" height="34" rx="17" class="f-marker"/>
      <line x1="24" y1="91" x2="452" y2="91" class="st"/>
      <circle cx="60" cy="91" r="10" class="f-ink"/>
      <circle cx="220" cy="91" r="15" class="f-ng"/>
      <text x="140" y="32" text-anchor="middle" class="big">RPO</text>
      <text x="140" y="56" text-anchor="middle" class="s">なくしてよいデータ</text>
      <text x="60" y="144" text-anchor="middle" class="t">セーブ</text>
      <text x="220" y="144" text-anchor="middle" class="t">停電</text>
    </svg>
  </figure>
  <p class="hitokoto">ゲームでいうと、RPO は<mark>最後のセーブから停電までに進めた分</mark>。</p>
  <p class="kichinto"><span class="label">きちんと言うと</span>RPO は障害の前を向き、失ってよいデータの量を時間で測ります。</p>
  <div class="mayoi"><span class="label">迷いどころ</span>どちらも時間で表すので、単位では見分けられません。失うデータの量か、復旧までの待ち時間かで見分けます。</div>
  <blockquote><span class="label">教科書の言葉</span><p>「時間で測ったデータ損失の許容量」</p></blockquote>
</article>
```

| 部品 | 規則 |
|---|---|
| `.qno` | 論点が属する見出し（`heading_path` のうち節の題） |
| `.chip` | 状態。卒業は `chip ok`、復習中は `chip ng` |
| `h2` | 論点を問いの形か短い題で書く |
| `.pic` | 大きな絵を 1 枚。必ず置く |
| `.hitokoto` | 1〜2 文のたとえ。いちばん覚えてほしい語句を `mark` で 1 か所だけ囲む |
| `.kichinto` | 2〜3 文。正確な言い方。原文に根拠がある内容だけを書く |
| `.mayoi` | 誤答経験のある論点にだけ置く。取り違えた 2 つを見分ける条件を書く。誤答の理由は推測しない |
| `blockquote` | 根拠になる原文を、必要最小限だけ引用する |

## 5. 絵の描き方

- 絵はインラインの SVG で描く。`viewBox` の幅は 480 にそろえ、高さは 180〜230 に収める。`role="img"` と、絵の内容を言葉にした `aria-label` を付ける。
- 色は雛形のクラスで付ける。`fill` や `stroke` に色を直接書かない。直接書くと、暗い表示で読めなくなる。

| クラス | 用途 |
|---|---|
| `st` | 線・矢印（塗りなし） |
| `sk` | 塗りのある図形の輪郭。`f-*` と組み合わせる |
| `f-paper` `f-tint` | 図形の塗り（地の色、淡い色） |
| `f-marker` | いちばん見せたい部分の塗り。1 枚に 1〜2 か所 |
| `f-ink` `f-blue` `f-ok` `f-ng` | 点や印の塗り |
| `t` `s` `big` | 文字（17px、13px、28px）。13px より小さい文字を使わない |
| `on-marker` | `f-marker` の上に置く文字 |

- 矢印の先は、`st` の短い線 2 本で描く。`<marker>` を使う場合は、`id` を論点ごとに変える（1 ページに複数の論点が並ぶため）。
- 文字は絵の中に 6 個程度までにする。文字どうし、文字と図形が重ならないよう、座標を決めてから書く。
- 順序や階層は、SVG の代わりに `rows` で書いてよい。並列の比較は `tiles` で書いてよい。どちらも `.pic` の中に置く。

```html
<figure class="pic">
  <ul class="rows">
    <li><b>標準</b><span>「玄関の鍵はディンプルキーを使う」</span><span class="tag">必須</span></li>
    <li class="hit"><b>ベースライン</b><span>「どの窓にも、最低でも補助錠を1つ付ける」</span><span class="tag">必須</span></li>
    <li><b>ガイドライン</b><span>「防犯砂利を敷くとより安心です」</span><span class="tag free">任意</span></li>
  </ul>
  <p class="cap">上から下へ具体的になります</p>
</figure>
```

```html
<figure class="pic">
  <div class="tiles">
    <div class="tile hit"><svg viewBox="0 0 52 52" aria-hidden="true"><rect x="11" y="9" width="30" height="36" rx="4" class="ico"/><path d="M18 28 l6 6 l11 -12" class="ico"/></svg><b>COBIT</b><span>監査・コンプライアンスの枠組み</span></div>
    <div class="tile"><svg viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="21" r="12" class="ico"/></svg><b>ISO/IEC 27001</b><span>ISMS の国際認証規格</span></div>
  </div>
</figure>
```

## 6. 文章の規則

- 事実の根拠は原文に限る。原文にない定義・数値・固有名詞を足さない。
- たとえ話は、原文にたとえがあればそれを使う。原文にないたとえを足してよいが、事実を増やさない。足したたとえがあることは、雛形のフッターが読者に伝えている。
- 1 文を短くする。ひとことは声に出して読める長さにする。

## 7. 書き直す条件

ノートは study.md に合わせる。載せるのは、挑戦済みで、アンカーが有効な論点（状態が `復習中` か `卒業`）である。状態が `要再抽出` の論点は書かない。次の 4 つを行い、それ以外の論点の `article` は書き直さない。

1. 載っていない論点の `article` を新しく書く。今回初めて挑戦した論点のほか、前回のセッションが途中で切れて書けなかった論点や、古い形式から移行した論点もこれに当たる。
2. `.chip` が study.md の状態と違う論点は、`.chip` を書き換える。
3. 誤答があるのに `.mayoi` がない論点、今回の誤答で迷いどころが変わった論点は、`.mayoi` を書き足す。
4. 状態が `要再抽出` になった論点の `article` は取り除く。根拠の段落が原文から失われているためである。進捗のリンクからも外す。

## 8. 確認

- [ ] 挑戦済みで状態が `復習中` か `卒業` の論点すべてに `article` があり、§4 の順に並んでいる。`要再抽出` の論点の `article` はない。
- [ ] `.chip` が study.md の状態と一致している。
- [ ] どの `article` にも絵（`.pic`）がある。
- [ ] 読者に見える文字に `topic-NNN` が出ていない。
- [ ] `fill` や `stroke` に色を直接書いていない。
- [ ] 外部の URL を `src` や `href`（ページ内リンクを除く）に書いていない。
- [ ] 進捗の分子が載せた論点の数、分母が `要再抽出` を除いた全論点の数と一致している。
- [ ] ノート全体が 1 つの言語で書かれ、ルート要素の `lang` 属性がその言語である（§9）。

## 9. 言語

ノートは、ユーザーの言語（依頼に使った言語。ユーザーが言語を指定したらその言語。判断できなければ日本語）で書く。原文の引用（`blockquote`）は資料の言語のままにする。

ノートがすでにあれば、そのノートの言語で書き続ける。ノートの言語は、ルート要素 `<html lang="…">` の `lang` 属性で分かる。ユーザーが別の言語を求めたときに限り、ノート全体をその言語で書き直す。

日本語以外の言語でノートを新しく作るときは、雛形を複製したあと、雛形の固定の文言もその言語に訳す。訳すのは次の 6 か所である。`<style>` の中は変更しない。

- ルート要素の `lang` 属性（例 `lang="en"`）
- `<title>` の資料名に続く部分（「絵解きノート」）
- `h1`
- 導入の段落（`.lead`）
- `.eyebrow` の「／ 最終更新」（全角の `／` を ` / ` に替え、「最終更新」を訳す。英語なら `{{SOURCE_NAME}} / Last updated {{UPDATED}}`）
- フッターの文

更新日（`{{UPDATED}}`）も、その言語の日付の書き方で書く（英語なら `October 4, 2026`）。

論点（`article`）の中の固定の見出しと、進捗の文言も、同じ言語で書く。study.md の論点の題名がノートの言語と違う言語で書かれていれば、`h2` や進捗のリンクには訳して書く。study.md の値は書き換えない。状態の表示（`.chip`）も同じ言語で書く。study.md の状態の値（`復習中`、`卒業`）は言語によらず決まった値だが、ノートにはそれを訳して表示する。CSS のクラス名（`chip ok`、`chip ng`、`label`、`mayoi` など）は、言語によらず変えない。

書き手どうしで文言がぶれないよう、日本語と英語では次の文言を使う。ほかの言語でも、これに相当する文言を一度決めたら、ノートの中で同じものを使い続ける。

| 日本語 | 英語 |
|---|---|
| 絵解きノート | Picture Notebook |
| 最終更新 | Last updated |
| 論点に挑戦済み | topics attempted |
| 復習中 | Reviewing |
| 卒業 | Mastered |
| きちんと言うと | Precisely |
| 迷いどころ | Where it gets confusing |
| 教科書の言葉 | In the source's words |
| 復習中の論点はありません。 | No topics under review. |

導入の段落とフッターの英語は、次のとおりにする（`{{SOURCE_NAME}}` は §2 と同じく資料のファイル名に置き換える）。

- 導入：`Look back at the topics you have attempted, each with one big picture and a few words. Precise definitions and formulas are in the textbook in the same folder (if there is no PDF, see the <code>.tex</code> manuscript).`
- フッター：`The correct answers and everything under "In the source's words" are based on {{SOURCE_NAME}}. Analogies that are not in the source were added for this notebook.`

英語の進捗は次のように書く。

```html
<div class="score">
  <p class="num"><b>17</b><span>/ 26 topics attempted</span></p>
  <p class="legend">Reviewing: <a href="#topic-012">How strict the five kinds of review are</a>, <a href="#topic-014">The baseline is the minimum</a></p>
</div>
```

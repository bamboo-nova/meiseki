# 出題データと回答の形式

## 1. ファイルと寿命

出題と回答のファイルは、対象資料の `.rikai/` に置く。名前の付け方は study.md と同じで、資料名が `.md` で終わるならその拡張子を置き換え、それ以外は元の名前に続けて付ける。

| 資料 | 出題データ | 出題フォーム | 回答 |
|---|---|---|---|
| `docs/report.md` | `docs/.rikai/report.quiz.json` | `docs/.rikai/report.quiz.html` | `docs/.rikai/report.answers.json` |
| `docs/report.pdf` | `docs/.rikai/report.pdf.quiz.json` | `docs/.rikai/report.pdf.quiz.html` | `docs/.rikai/report.pdf.answers.json` |

3 つともセッション中だけのファイルである。study.md を保存したら、すぐに削除する。

## 2. 出題データ（quiz.json）

出題データは正解を含み、採点の正本になる。モデルが書くのはこのファイルだけで、フォームは `scripts/build_quiz.py` が組み立てる。

```json
{
  "format": 1,
  "session_id": "session-20261004-164530",
  "title": "report.md の理解度チェック",
  "questions": [
    {
      "no": 1,
      "topic_id": "topic-001",
      "title": "通常キャッシュの有効期限",
      "anchor": {
        "heading_path": ["キャッシュ方針", "有効期限"],
        "quote": "キャッシュの有効期限は通常 10 分とする。",
        "line": 12
      },
      "aspect": "主張の識別",
      "question": "通常のキャッシュの有効期限はどれですか。",
      "choices": [
        {"id": "a", "text": "5 分"},
        {"id": "b", "text": "10 分"},
        {"id": "c", "text": "無期限"}
      ],
      "correct": "b"
    }
  ]
}
```

| キー | 規則 |
|---|---|
| `format` | 整数 `1` |
| `session_id` | `session-YYYYMMDD-HHMMSS`（出題データを書く時点の現在時刻）。挑戦履歴の `session_id` に同じ値を書く |
| `title` | フォームの見出し。ユーザーの言語で「資料名 の理解度チェック」とする（英語なら `report.md comprehension check`） |
| `lang` | 省略できる。問題・選択肢を書いた言語（ユーザーの言語）の言語タグ（`ja`、`en`、`ko`、`pt-BR` など）。省略すると `ja` として扱う |
| `ui` | 省略できる。フォームの固定の文言を上書きするオブジェクト。キーは下の表のキーに限り、値は空でない文字列にする。表にないキーは誤りとして止まる |
| `questions[].no` | 1 から始まる連番。フォームを組み立てるときに、問題の順番ごと振り直される |
| `questions[].topic_id` | study.md の論点 id。同じ論点は 1 セッションに 1 回だけ出す。初めて抽出した論点は、ここで割り当てた id を study.md でも使う |
| `questions[].title` | 論点の題名（空でない文字列）。study.md の論点の `title` と同じ値を書く |
| `questions[].anchor` | 論点のアンカー。`heading_path`（空でない文字列を 1 つ以上並べた配列）、`quote`（空でない文字列）、`line`（1 以上の整数か `null`）を持つ。study.md の論点の `anchor` と同じ値を書く |
| `questions[].aspect` | 問うた観点。挑戦履歴の `aspect` に同じ値を書く |
| `questions[].question` | 問題文 |
| `questions[].choices` | 選択肢。2 件以上。`id` は半角の小文字英数字で、同じ問の中で重ならないようにする |
| `questions[].correct` | 正解の選択肢の `id` |

`title` と `anchor` は、study.md にまだない論点を出題データだけから復元できるようにするために書く。初回のセッションでは、新しく抽出した論点は採点後の保存まで study.md にないので、途中で切れたときの再開（§5）にはこの 2 つが要る。

`questions` の並びと `no`、各問の `choices` と `correct` は、フォームを組み立てるときに `scripts/build_quiz.py` が書き換える。まず問題の順番を無作為に並べ替え、`no` を 1 から振り直す。出題データは復習問題を優先して選んだ順で書かれるので、そのまま出すと、どれが復習問題かが解く前に分かるためである。次に各問の選択肢を並べ替え、新しい順に `id` を `a`、`b`、`c` と振り直し、`correct` を同じ選択肢に付け替えて、出題データのファイルに書き戻す。採点と挑戦履歴には、書き戻したあとのファイルを使う。モデルは問題も選択肢もどの順で書いてよい。ブラウザを使えず問題をテキストで提示する場合も、`python3` があれば先に `build_quiz.py` を実行する。テキストで提示するときは、その直前に出題データを読み直し、書かれている順と id のまま提示する。

フォームに載るのは `session_id`、`title`、`lang`、`ui`、各問の `no`・`question`・`choices` だけである。`correct`、`topic_id`、各問の `title`・`anchor`、`aspect` は載らない。

### 2.1 言語とフォームの文言

問題文、選択肢、`title` はユーザーの言語で書く（SKILL.md §2）。`lang` にはその言語を書く。フォームの固定の文言（見出しの上の小さな文字、ボタン、案内など）は `lang` で選ばれる。主の言語（`pt-BR` なら `pt`）が `ja` なら日本語、それ以外は英語の組み込みの文言になり、そのうえに `ui` の値が上書きされる。日本語と英語以外の言語では、下の表のキーをすべて `ui` に書く。書かなかったキーは英語のまま表示される。

| キー | 日本語（組み込み） | 英語（組み込み） |
|---|---|---|
| `eyebrow` | rikai 理解度チェック | rikai comprehension check |
| `meta` | 全 {total} 問。すべてに答えると提出できます。 | Questions: {total}. Answer all of them to submit. |
| `question` | 問{no} | Q{no} |
| `progress` | {answered} / {total} 問に回答 | {answered} / {total} answered |
| `submit` | 提出する | Submit |
| `done_title` | 提出しました | Submitted |
| `done_body` | ターミナルに戻ると採点結果が出ます。このタブは閉じてかまいません。 | Go back to the terminal to see your results. You can close this tab. |
| `paste_title` | 回答コードをターミナルに貼ってください | Paste the answer code into the terminal |
| `paste_note` | 下のコードをコピーして、ターミナルに貼り付けてください。 | Copy the code below and paste it into the terminal. |
| `copy` | コピーする | Copy |
| `copied` | 回答コードをコピーしました。ターミナルに貼り付けてください。 | Answer code copied. Paste it into the terminal. |
| `selected` | コードを選択しました。コピーしてターミナルに貼り付けてください。 | Code selected. Copy it and paste it into the terminal. |
| `code_label` | 回答コード | Answer code |

`code_label` は、回答コードの欄を読み上げるときの名前（`aria-label`）である。`{total}`（問題数）、`{no}`（問題番号）、`{answered}`（答えた数）は、フォームが値に置き換える。`ui` に書く文言にも、同じ書き方で入れてよい。例えば韓国語なら、出題データの最上位に次のように書く。

```json
"lang": "ko",
"ui": {
  "eyebrow": "rikai 이해도 확인",
  "meta": "총 {total}문항. 모두 답하면 제출할 수 있습니다.",
  "question": "문제 {no}",
  "progress": "{answered} / {total}문항 답함",
  "submit": "제출",
  "done_title": "제출했습니다",
  "done_body": "터미널로 돌아가면 채점 결과가 나옵니다. 이 탭은 닫아도 됩니다.",
  "paste_title": "답안 코드를 터미널에 붙여 넣어 주세요",
  "paste_note": "아래 코드를 복사해서 터미널에 붙여 넣어 주세요.",
  "copy": "복사",
  "copied": "답안 코드를 복사했습니다. 터미널에 붙여 넣어 주세요.",
  "selected": "코드를 선택했습니다. 복사해서 터미널에 붙여 넣어 주세요.",
  "code_label": "답안 코드"
}
```

## 3. 回答（answers.json）

`scripts/quiz_server.py` が書く。モデルは読むだけである。

```json
{
  "format": 1,
  "session_id": "session-20261004-164530",
  "submitted_at": "2026-10-04T16:49:15+09:00",
  "via": "server",
  "answers": {"1": "b", "2": "a"}
}
```

`via` は `server`（フォームから受け取った）か `code`（回答コードから作った）のどちらかである。`answers` のキーは問題番号の文字列、値は選んだ選択肢の `id` である。`session_id` が出題データと違う回答は、別のセッションのものなので採点に使わない。

## 4. 回答コード

サーバへ送れないとき、フォームは回答コードを表示する。形式は `問題番号:選択肢の id` を空白で区切ったものである。

```text
1:b 2:a 3:c
```

ユーザーが貼ったコードは、次のコマンドで回答ファイルにする。全角文字、改行区切り、カンマ区切りはスクリプトが吸収する。

```bash
python3 "<SKILL_DIR>/scripts/quiz_server.py" code --data "<出題データ>" --out "<回答ファイル>" --code '1:b 2:a 3:c'
```

貼り付けられた文字列は単一引用符で囲み、二重引用符に入れない。シェルが `$` やバッククォートを解釈するためである。確実なのは `-` を指定して標準入力から渡す方法である（`--code -`。例 `printf '%s\n' '1:b 2:a 3:c' | python3 "<SKILL_DIR>/scripts/quiz_server.py" code --data "<出題データ>" --out "<回答ファイル>" --code -`）。

終了コード 1 は、貼られたコードが出題データと合わないことを示す（読み取れない、問が欠けている、選択肢にない id がある）。表示された誤りをユーザーに伝えてもう一度貼ってもらう。回答を補ったり推測したりしてはならない。

## 5. 途中で切れたセッションの再開

起動時に `.rikai/` に出題データが残っていたら、前回のセッションが途中で切れている。新しい問題は作らず、次の表を上から順に見て、最初に当てはまる行の位置から再開する。

| 状況 | 再開する位置 |
|---|---|
| study.md の挑戦履歴に、出題データと同じ `session_id` がある | 採点と保存は済んでいる。採点せずに、残っている出題データ・出題フォーム・回答ファイルを削除する。その `session_id` を持つ study.md の挑戦履歴から、そのセッションの結果の表（SKILL.md の Step 5 と同じ列）を出してから、explainer の更新に進む |
| 出題データと回答がある | 採点から |
| 出題データだけがある | フォームの組み立てと回答の受け取りから。出題フォームも残っていれば、`build_quiz.py` に `--no-shuffle` を付けて組み立て直す（選択肢はすでに並べ替えて書き戻してある。並べ直すと、開いたままのタブやブラウザに保存された途中の回答と id が食い違う） |

study.md にまだない `topic_id` は、出題データの `title` と `anchor` から論点を復元してから採点する。

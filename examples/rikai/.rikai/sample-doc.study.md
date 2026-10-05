---
schema_version: 3
source_path: ../sample-doc.md
topics:
  - id: topic-001
    title: 一意キーと重複の防止
    anchor:
      heading_path:
        - 通知配信ワーカーの再送設計
        - 2. 受付
        - 2.1 重複の防止
      quote: 送信要求には、呼び出し元が利用者 ID と通知種別から作った一意キーを付ける。
      line: 13
    status: 復習中
    attempts:
      - attempted_at: "2026-09-18T09:00:00+09:00"
        correct: false
        question: 同じ一意キーを持つ送信要求を再度受け付けたとき、ワーカーはどうしますか。
        aspect: 主張の識別
        choices:
          - id: "1"
            text: 新しいジョブを作り、新しい ID を返す
          - id: "2"
            text: 新しいジョブを作らず、既存ジョブの ID を返す
          - id: "3"
            text: 要求を破棄し、ID は返さない
        user_answer:
          choice_id: "1"
          reasoning: 再度受け付けた要求は別の処理として登録されると思いました。
        session_id: session-20260918-0900
      - attempted_at: "2026-09-19T09:00:00+09:00"
        correct: true
        question: 一意キー `K1` の要求が受理済みで、同じ `K1` の要求が届きました。原文に合う結果はどれですか。
        aspect: 具体例への適用
        choices:
          - id: "1"
            text: 受理済みジョブの ID が返る
          - id: "2"
            text: 二つのジョブが一つに結合される
          - id: "3"
            text: 受理済みジョブが取り消される
        user_answer:
          choice_id: "1"
          reasoning: null
        session_id: session-20260919-0900
      - attempted_at: "2026-09-20T09:00:00+09:00"
        correct: true
        question: 重複防止の規則を働かせるために、呼び出し元が満たす必要がある条件はどれですか。
        aspect: 前提条件
        choices:
          - id: "1"
            text: 再送のたびに一意キーを作り直す
          - id: "2"
            text: 最初の要求と再送要求で同じ一意キーを使う
          - id: "3"
            text: 通知種別だけを一意キーとして使う
        user_answer:
          choice_id: "2"
          reasoning: null
        session_id: session-20260920-0900
  - id: topic-002
    title: 配信順序は保証されない
    anchor:
      heading_path:
        - 通知配信ワーカーの再送設計
        - 2. 受付
        - 2.2 配信順序
      quote: ワーカーは同じ利用者へのジョブを受付順に保存するが、配信の完了順は保証しない。
      line: 19
    status: 卒業
    attempts:
      - attempted_at: "2026-09-18T09:05:00+09:00"
        correct: true
        question: 同じ利用者へのジョブについて、保証される順序はどれですか。
        aspect: 主張の識別
        choices:
          - id: "1"
            text: 受付順での保存
          - id: "2"
            text: 受付順での配信完了
          - id: "3"
            text: 通知種別順での配信完了
        user_answer:
          choice_id: "1"
          reasoning: null
        session_id: session-20260918-0900
      - attempted_at: "2026-09-19T09:10:00+09:00"
        correct: false
        question: 後から受け付けたジョブが先に完了し得るのは、どのような場合ですか。
        aspect: 例外を生む条件
        choices:
          - id: "1"
            text: 先のジョブが再送待ちになった場合
          - id: "2"
            text: 先のジョブが受付順に保存された場合
          - id: "3"
            text: 後のジョブに同じ利用者 ID がある場合
        user_answer:
          choice_id: "2"
          reasoning: 受付順に保存するなら、完了も同じ順になると思いました。
        session_id: session-20260919-0900
      - attempted_at: "2026-09-20T09:10:00+09:00"
        correct: true
        question: ジョブ A の後にジョブ B を受け付け、A だけが再送待ちになりました。原文で許容される結果はどれですか。
        aspect: 具体例への適用
        choices:
          - id: "1"
            text: B が A より先に完了する
          - id: "2"
            text: B は A が完了するまで保存されない
          - id: "3"
            text: A と B の受付順が入れ替わる
        user_answer:
          choice_id: "1"
          reasoning: null
        session_id: session-20260920-0900
      - attempted_at: "2026-09-21T09:00:00+09:00"
        correct: true
        question: 原文の保証範囲を広げすぎている説明はどれですか。
        aspect: 誤った一般化の判別
        choices:
          - id: "1"
            text: ジョブは受付順に保存される
          - id: "2"
            text: ジョブは受付順に完了する
          - id: "3"
            text: 再送待ちにより後のジョブが先に完了し得る
        user_answer:
          choice_id: "2"
          reasoning: null
        session_id: session-20260921-0900
  - id: topic-003
    title: 再送対象の判定（502/503/タイムアウト）
    anchor:
      heading_path:
        - 通知配信ワーカーの再送設計
        - 3. 再送
        - 3.1 再送の対象
      quote: 外部 API が `502` または `503` を返した場合と、接続がタイムアウトした場合は再送する。
      line: 25
    status: 復習中
    attempts:
      - attempted_at: "2026-09-18T09:10:00+09:00"
        correct: false
        question: 一時的な失敗として再送する組み合わせはどれですか。
        aspect: 主張の識別
        choices:
          - id: "1"
            text: "`502`、`503`、接続タイムアウト"
          - id: "2"
            text: "`400`、`404`、接続タイムアウト"
          - id: "3"
            text: "`400`、`502`、認証失敗"
        user_answer:
          choice_id: "2"
          reasoning: タイムアウトとすべてのエラー応答が再送対象だと思いました。
        session_id: session-20260918-0900
      - attempted_at: "2026-09-19T09:20:00+09:00"
        correct: true
        question: 外部 API への接続がタイムアウトしました。ワーカーの次の処理として原文に合うものはどれですか。
        aspect: 具体例への適用
        choices:
          - id: "1"
            text: 一時的な失敗として再送する
          - id: "2"
            text: 成功として完了を記録する
          - id: "3"
            text: 要求内容の誤りとして確定する
        user_answer:
          choice_id: "1"
          reasoning: null
        session_id: session-20260919-0900
      - attempted_at: "2026-09-20T09:20:00+09:00"
        correct: false
        question: "`503` 応答を受けたときの失敗分類と処理の関係はどれですか。"
        aspect: 因果関係
        choices:
          - id: "1"
            text: 一時的な失敗として扱うため再送する
          - id: "2"
            text: 要求内容の失敗として扱うため確定する
          - id: "3"
            text: 成功応答として扱うため記録する
        user_answer:
          choice_id: "2"
          reasoning: "`503` は応答が返っているので一時的な失敗ではないと思いました。"
        session_id: session-20260920-0900
  - id: topic-004
    title: 429 は「再送しない」の例外
    anchor:
      heading_path:
        - 通知配信ワーカーの再送設計
        - 3. 再送
        - 3.1 再送の対象
      quote: "`429` を除く `4xx` 応答は再送しない。"
      line: 27
    status: 卒業
    attempts:
      - attempted_at: "2026-09-19T09:40:00+09:00"
        correct: true
        question: "`4xx` 応答のうち、再送しないという通常則の例外はどれですか。"
        aspect: 例外条件
        choices:
          - id: "1"
            text: "`400`"
          - id: "2"
            text: "`404`"
          - id: "3"
            text: "`429`"
        user_answer:
          choice_id: "3"
          reasoning: null
        session_id: session-20260919-0900
  - id: topic-005
    title: 試行上限と失敗キュー
    anchor:
      heading_path:
        - 通知配信ワーカーの再送設計
        - 3. 再送
        - 3.2 待機時間と上限
      quote: 再送前の待機時間は 1 秒、2 秒、4 秒の順に延ばし、その後は 8 秒を上限とする。
      line: 31
    status: 卒業
    attempts:
      - attempted_at: "2026-09-18T09:15:00+09:00"
        correct: true
        question: 最初の三回の再送前に使う待機時間の順序はどれですか。
        aspect: 手順の順序
        choices:
          - id: "1"
            text: 1 秒、2 秒、4 秒
          - id: "2"
            text: 2 秒、4 秒、8 秒
          - id: "3"
            text: 4 秒、2 秒、1 秒
        user_answer:
          choice_id: "1"
          reasoning: null
        session_id: session-20260918-0900
  - id: topic-006
    title: 完了判定と保存失敗
    anchor:
      heading_path:
        - 通知配信ワーカーの再送設計
        - 4. 完了と停止
        - 4.1 完了の判定
      quote: 外部 API が成功応答を返し、その応答 ID を配信記録へ保存できた時点で、ジョブを完了とする。
      line: 39
    status: 復習中
    attempts:
      - attempted_at: "2026-09-18T09:20:00+09:00"
        correct: false
        question: ジョブを完了とするために必要な組み合わせはどれですか。
        aspect: 完了条件
        choices:
          - id: "1"
            text: 成功応答を受け取り、応答 ID の保存にも成功する
          - id: "2"
            text: 成功応答を受け取るが、応答 ID の保存には失敗する
          - id: "3"
            text: 応答を受け取らず、要求の受付だけを記録する
        user_answer:
          choice_id: "2"
          reasoning: 外部 API が成功なら保存結果に関係なく完了だと思いました。
        session_id: session-20260918-0900
      - attempted_at: "2026-09-19T09:30:00+09:00"
        correct: true
        question: 成功応答の受信後に応答 ID の保存へ失敗しました。このジョブの状態はどうなりますか。
        aspect: 例外への適用
        choices:
          - id: "1"
            text: 完了にする
          - id: "2"
            text: 完了にしない
          - id: "3"
            text: 成功応答を失敗応答へ変更する
        user_answer:
          choice_id: "2"
          reasoning: null
        session_id: session-20260919-0900
  - id: topic-007
    title: 緊急停止の例外
    anchor:
      heading_path:
        - 通知配信ワーカーの再送設計
        - 4. 完了と停止
        - 4.2 運用停止
      quote: 運用者が配信を停止すると、新しいジョブの取得を止める。
      line: 45
    status: 卒業
    attempts:
      - attempted_at: "2026-09-20T09:40:00+09:00"
        correct: true
        question: 通常の運用停止時、すでに外部 API へ送信中の要求をどう扱いますか。
        aspect: 停止時の手順
        choices:
          - id: "1"
            text: 直ちに取り消し、応答を待たない
          - id: "2"
            text: 応答を記録してからワーカーを停止する
          - id: "3"
            text: 新しいジョブとして受付キューへ戻す
        user_answer:
          choice_id: "2"
          reasoning: null
        session_id: session-20260920-0900
  - id: topic-008
    title: 旧版・保守時間（アンカー切れ）
    anchor:
      heading_path:
        - 通知配信ワーカーの再送設計
        - 5. 保守時間
      quote: 毎日 2 時から 3 時までは新しい配信を受け付けない。
      line: 51
    status: 要再抽出
    attempts:
      - attempted_at: "2026-09-17T15:00:00+09:00"
        correct: false
        question: 保守時間中の新しい配信要求はどう扱いますか。
        aspect: 適用条件
        choices:
          - id: "1"
            text: 通常どおり受け付ける
          - id: "2"
            text: 新しい配信を受け付けない
          - id: "3"
            text: 成功として記録する
        user_answer:
          choice_id: "1"
          reasoning: 保守中も受付だけは続けると思いました。
        session_id: session-20260917-1500
---

# 学習記録

このファイルは meiseki:rikai（読解度チェックスキル）が生成した学習記録です。資料「sample-doc.md」から抽出した論点（topic ＝ 出題単位。資料の主張・前提・例外のひとまとまり）ごとに、出題履歴と状態を frontmatter に記録しています。状態は 3 種類あり、復習中は今後も出題される論点、卒業は理解済みとして出題されない論点、要再抽出は原文の改稿で根拠箇所を見失った論点です。論点の解説は、同じフォルダの絵解きノート（sample-doc.explainer.html）とテキストブック（sample-doc.explainer.pdf）にあります。下の「書き手への還流レポート」は誤読が集中した段落の一覧で、資料の書き手が明晰化の入力に使えます。

## 書き手への還流レポート

1. 論点: 再送対象の判定（502/503/タイムアウト）
   - 誤答回数: 2
   - 最終誤答日時: `2026-09-20T09:20:00+09:00`
   - 見出しパス: `通知配信ワーカーの再送設計 > 3. 再送 > 3.1 再送の対象`
   - 引用: 「外部 API が `502` または `503` を返した場合と、接続がタイムアウトした場合は再送する。」
2. 論点: 配信順序は保証されない
   - 誤答回数: 1
   - 最終誤答日時: `2026-09-19T09:10:00+09:00`
   - 見出しパス: `通知配信ワーカーの再送設計 > 2. 受付 > 2.2 配信順序`
   - 引用: 「ワーカーは同じ利用者へのジョブを受付順に保存するが、配信の完了順は保証しない。」
3. 論点: 完了判定と保存失敗
   - 誤答回数: 1
   - 最終誤答日時: `2026-09-18T09:20:00+09:00`
   - 見出しパス: `通知配信ワーカーの再送設計 > 4. 完了と停止 > 4.1 完了の判定`
   - 引用: 「外部 API が成功応答を返し、その応答 ID を配信記録へ保存できた時点で、ジョブを完了とする。」
4. 論点: 一意キーと重複の防止
   - 誤答回数: 1
   - 最終誤答日時: `2026-09-18T09:00:00+09:00`
   - 見出しパス: `通知配信ワーカーの再送設計 > 2. 受付 > 2.1 重複の防止`
   - 引用: 「送信要求には、呼び出し元が利用者 ID と通知種別から作った一意キーを付ける。」
5. 論点: 旧版・保守時間（アンカー切れ）
   - 誤答回数: 1
   - 最終誤答日時: `2026-09-17T15:00:00+09:00`
   - 見出しパス: `通知配信ワーカーの再送設計 > 5. 保守時間`
   - 引用: 「毎日 2 時から 3 時までは新しい配信を受け付けない。」

誤答総数: 6

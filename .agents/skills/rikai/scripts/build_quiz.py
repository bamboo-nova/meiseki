#!/usr/bin/env python3
"""出題データ(quiz.json)を検証し、出題フォーム(quiz.html)を組み立てる。

使い方:
    python3 build_quiz.py --data report.quiz.json --out report.quiz.html

出題データは正解を含む採点の正本。フォームには問題文と選択肢だけを載せる。
既定では各問の選択肢を並べ替え、id を a, b, c … に振り直して出題データへ書き戻してから
フォームを組み立てる(--no-shuffle で並べ替えも書き戻しもしない)。採点は書き戻した出題データで行う。
出題データの lang(言語タグ。既定 ja)と ui(固定の文言の上書き)はそのままフォームに渡す。
標準ライブラリだけで動く。終了コード: 0=成功 / 1=入力の誤り
"""
import argparse
import copy
import json
import os
import random
import re
import sys

PLACEHOLDER = "/*__QUIZ_DATA__*/"
TEMPLATE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "quiz-template.html"
)
CHOICE_ID = re.compile(r"^[a-z0-9]+$")
LANG_TAG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]+)*$")
DEFAULT_LANG = "ja"
# フォームの固定の文言のキー。雛形の組み込み表(ja と en)と同じ集合にする。ui で上書きできる
UI_KEYS = (
    "eyebrow", "meta", "question", "progress", "submit", "done_title", "done_body",
    "paste_title", "paste_note", "copy", "copied", "selected", "code_label",
)


class QuizError(ValueError):
    """出題データが形式に合わないときに送出する。"""


def _require_text(obj, key, where):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QuizError(f"{where}: {key} は空でない文字列にしてください")
    return value


def _require_anchor(q, where):
    anchor = q.get("anchor")
    if not isinstance(anchor, dict):
        raise QuizError(f"{where}: anchor はオブジェクトにしてください")
    path = anchor.get("heading_path")
    if not isinstance(path, list) or not path or not all(isinstance(h, str) and h.strip() for h in path):
        raise QuizError(f"{where}: anchor.heading_path は空でない文字列を 1 つ以上並べた配列にしてください")
    _require_text(anchor, "quote", f"{where}: anchor")
    if "line" not in anchor:
        raise QuizError(f"{where}: anchor.line を書いてください(行番号が分からなければ null)")
    line = anchor["line"]
    if line is not None and (isinstance(line, bool) or not isinstance(line, int) or line < 1):
        raise QuizError(f"{where}: anchor.line は 1 以上の整数か null にしてください")


def _check_language(data):
    if "lang" in data:
        lang = data["lang"]
        if not isinstance(lang, str) or not LANG_TAG.match(lang):
            raise QuizError("lang は「ja」「en」「pt-BR」のような言語タグにしてください")
    if "ui" in data:
        ui = data["ui"]
        if not isinstance(ui, dict):
            raise QuizError("ui はオブジェクトにしてください")
        unknown = sorted(k for k in ui if k not in UI_KEYS)
        if unknown:
            raise QuizError("ui に知らないキーがあります: " + ", ".join(unknown) + "(使えるキー: " + ", ".join(UI_KEYS) + ")")
        for key in UI_KEYS:
            if key in ui:
                _require_text(ui, key, "ui")


def validate_quiz(data):
    """出題データを検証し、同じ辞書を返す。問題があれば QuizError を送出する。"""
    if not isinstance(data, dict):
        raise QuizError("出題データはオブジェクトにしてください")
    if data.get("format") != 1:
        raise QuizError("format は 1 にしてください")
    for key in ("session_id", "title"):
        _require_text(data, key, "出題データ")
    _check_language(data)
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise QuizError("questions は 1 問以上の配列にしてください")
    seen_topics = set()
    for index, q in enumerate(questions, 1):
        where = f"{index} 問目"
        if not isinstance(q, dict):
            raise QuizError(f"{where}: オブジェクトにしてください")
        if q.get("no") != index:
            raise QuizError(f"{where}: no は {index} にしてください")
        for key in ("topic_id", "title", "aspect", "question", "correct"):
            _require_text(q, key, where)
        _require_anchor(q, where)
        if q["topic_id"] in seen_topics:
            raise QuizError(f"{where}: 論点 {q['topic_id']} を 2 回出題しています")
        seen_topics.add(q["topic_id"])
        choices = q.get("choices")
        if not isinstance(choices, list) or len(choices) < 2:
            raise QuizError(f"{where}: choices は 2 件以上にしてください")
        ids = []
        for c in choices:
            if not isinstance(c, dict):
                raise QuizError(f"{where}: 選択肢はオブジェクトにしてください")
            choice_id = _require_text(c, "id", where)
            if not CHOICE_ID.match(choice_id):
                raise QuizError(f"{where}: 選択肢の id は半角の小文字英数字にしてください")
            _require_text(c, "text", where)
            ids.append(choice_id)
        if len(set(ids)) != len(ids):
            raise QuizError(f"{where}: 選択肢の id が重複しています")
        if q["correct"] not in ids:
            raise QuizError(f"{where}: correct が選択肢の id と一致しません")
    return data


def shuffle_choices(data, rng=None):
    """各問の選択肢を並べ替えた複製を返す。id は新しい順に a, b, c … と振り直し、
    correct は並べ替え前と同じ文の選択肢を指す。元のデータは変えない。"""
    rng = rng or random.SystemRandom()
    result = copy.deepcopy(data)
    for q in result["questions"]:
        choices = list(q["choices"])
        if len(choices) > 26:
            raise QuizError(f"{q['no']} 問目: 選択肢は 26 件までにしてください")
        correct = next(c for c in choices if c["id"] == q["correct"])
        rng.shuffle(choices)
        for i, c in enumerate(choices):
            c["id"] = chr(ord("a") + i)
        q["choices"] = choices
        q["correct"] = correct["id"]
    return result


def shuffle_questions(data, rng=None):
    """問題の順番を並べ替えた複製を返す。no は新しい順に 1 から振り直す。元のデータは変えない。

    出題データは「復習問題を優先して選んだ順」で書かれる。その順のまま出すと、
    どれが復習問題かが解く前に分かるので、出す順番は無作為にする。
    """
    rng = rng or random.SystemRandom()
    result = copy.deepcopy(data)
    questions = list(result["questions"])
    rng.shuffle(questions)
    for no, q in enumerate(questions, 1):
        q["no"] = no
    result["questions"] = questions
    return result


def write_json(path, data):
    """途中で切れても壊れたファイルが残らないよう、別名に書き終えてから置き換える。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def public_payload(data):
    """フォームに載せてよい部分だけを取り出す。正解・論点 id・観点は載せない。"""
    return {
        "session_id": data["session_id"],
        "title": data["title"],
        "lang": data.get("lang", DEFAULT_LANG),
        "ui": dict(data.get("ui", {})),
        "questions": [
            {
                "no": q["no"],
                "question": q["question"],
                "choices": [{"id": c["id"], "text": c["text"]} for c in q["choices"]],
            }
            for q in data["questions"]
        ],
    }


def embed_json(payload):
    """script 要素の中へ安全に埋め込める JSON 文字列を返す。"""
    text = json.dumps(payload, ensure_ascii=False)
    for raw, escaped in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        (chr(0x2028), "\\u2028"),
        (chr(0x2029), "\\u2029"),
    ):
        text = text.replace(raw, escaped)
    return text


def render_html(data, template_text):
    """雛形の差し込み位置に、公開してよい出題内容を埋め込む。"""
    if template_text.count(PLACEHOLDER) != 1:
        raise QuizError("雛形には差し込み位置がちょうど 1 つ必要です")
    return template_text.replace(PLACEHOLDER, embed_json(public_payload(data)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="出題データから出題フォームを組み立てる")
    ap.add_argument("--data", required=True, help="出題データ(quiz.json)")
    ap.add_argument("--out", required=True, help="出力するフォーム(quiz.html)")
    ap.add_argument("--template", default=TEMPLATE, help="フォームの雛形")
    ap.add_argument(
        "--no-shuffle", action="store_true", help="問題の順番も選択肢も並べ替えず、出題データも書き戻さない"
    )
    args = ap.parse_args(argv)
    try:
        with open(args.data, encoding="utf-8") as f:
            data = validate_quiz(json.load(f))
        with open(args.template, encoding="utf-8") as f:
            template = f.read()
        if not args.no_shuffle:
            data = validate_quiz(shuffle_questions(shuffle_choices(data)))
            write_json(args.data, data)
        html = render_html(data, template)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[build_quiz] {e}\n")
        return 1
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[build_quiz] {len(data['questions'])} 問のフォームを書き出しました: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

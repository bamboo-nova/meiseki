import copy
import json
import os
import random
import re
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.join(REPO, ".agents", "skills", "rikai")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import build_quiz  # noqa: E402

TEMPLATE = os.path.join(SKILL, "assets", "quiz-template.html")


def sample_quiz():
    return {
        "format": 1,
        "session_id": "session-20261004-01",
        "title": "report.md の理解度チェック",
        "questions": [
            {
                "no": 1,
                "topic_id": "topic-001",
                "title": "通常時のキャッシュ有効期限",
                "anchor": {
                    "heading_path": ["2. キャッシュ"],
                    "quote": "通常時の有効期限は 10 分とする。",
                    "line": 12,
                },
                "aspect": "主張の識別",
                "question": "通常のキャッシュの有効期限はどれですか。",
                "choices": [
                    {"id": "a", "text": "5 分"},
                    {"id": "b", "text": "10 分"},
                    {"id": "c", "text": "無期限"},
                ],
                "correct": "b",
            },
            {
                "no": 2,
                "topic_id": "topic-002",
                "title": "障害対応中の短縮",
                "anchor": {
                    "heading_path": ["2. キャッシュ", "2.1 例外"],
                    "quote": "障害対応中は 1 分に短縮する。",
                    "line": None,
                },
                "aspect": "例外条件",
                "question": "障害対応中の有効期限はどれですか。",
                "choices": [
                    {"id": "a", "text": "1 分"},
                    {"id": "b", "text": "10 分"},
                ],
                "correct": "a",
            },
        ],
    }


def embedded_payload(html):
    m = re.search(r'<script type="application/json" id="quiz-data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


class ValidateTest(unittest.TestCase):
    def test_valid_quiz_passes(self):
        data = sample_quiz()
        self.assertIs(build_quiz.validate_quiz(data), data)

    def test_correct_must_be_one_of_the_choices(self):
        data = sample_quiz()
        data["questions"][0]["correct"] = "z"
        with self.assertRaises(build_quiz.QuizError):
            build_quiz.validate_quiz(data)

    def test_choice_ids_must_be_unique(self):
        data = sample_quiz()
        data["questions"][0]["choices"][1]["id"] = "a"
        with self.assertRaises(build_quiz.QuizError):
            build_quiz.validate_quiz(data)

    def test_choice_id_must_be_lowercase_alphanumeric(self):
        data = sample_quiz()
        data["questions"][0]["choices"][0]["id"] = "A"
        with self.assertRaises(build_quiz.QuizError):
            build_quiz.validate_quiz(data)

    def test_question_numbers_must_be_sequential(self):
        data = sample_quiz()
        data["questions"][1]["no"] = 3
        with self.assertRaises(build_quiz.QuizError):
            build_quiz.validate_quiz(data)

    def test_same_topic_cannot_appear_twice(self):
        data = sample_quiz()
        data["questions"][1]["topic_id"] = "topic-001"
        with self.assertRaises(build_quiz.QuizError):
            build_quiz.validate_quiz(data)

    def test_at_least_two_choices(self):
        data = sample_quiz()
        data["questions"][1]["choices"] = data["questions"][1]["choices"][:1]
        with self.assertRaises(build_quiz.QuizError):
            build_quiz.validate_quiz(data)

    def test_empty_questions_rejected(self):
        data = sample_quiz()
        data["questions"] = []
        with self.assertRaises(build_quiz.QuizError):
            build_quiz.validate_quiz(data)

    def test_topic_title_is_required(self):
        for bad in (None, "", "  ", 3):
            data = sample_quiz()
            if bad is None:
                del data["questions"][0]["title"]
            else:
                data["questions"][0]["title"] = bad
            with self.subTest(title=bad), self.assertRaises(build_quiz.QuizError):
                build_quiz.validate_quiz(data)

    def test_anchor_is_required_and_checked(self):
        def broken(edit):
            data = sample_quiz()
            edit(data["questions"][0])
            return data

        cases = {
            "missing": lambda q: q.pop("anchor"),
            "not an object": lambda q: q.__setitem__("anchor", "2. キャッシュ"),
            "no heading_path": lambda q: q["anchor"].pop("heading_path"),
            "empty heading_path": lambda q: q["anchor"].__setitem__("heading_path", []),
            "heading_path not a list": lambda q: q["anchor"].__setitem__("heading_path", "2. キャッシュ"),
            "empty heading": lambda q: q["anchor"].__setitem__("heading_path", ["2. キャッシュ", " "]),
            "no quote": lambda q: q["anchor"].pop("quote"),
            "empty quote": lambda q: q["anchor"].__setitem__("quote", ""),
            "no line": lambda q: q["anchor"].pop("line"),
            "line zero": lambda q: q["anchor"].__setitem__("line", 0),
            "line text": lambda q: q["anchor"].__setitem__("line", "12"),
            "line bool": lambda q: q["anchor"].__setitem__("line", True),
        }
        for name, edit in cases.items():
            with self.subTest(case=name), self.assertRaises(build_quiz.QuizError):
                build_quiz.validate_quiz(broken(edit))

    def test_anchor_line_may_be_null(self):
        data = sample_quiz()
        self.assertIsNone(data["questions"][1]["anchor"]["line"])
        self.assertIs(build_quiz.validate_quiz(data), data)


class LanguageTest(unittest.TestCase):
    def test_lang_and_ui_are_optional(self):
        data = sample_quiz()
        self.assertNotIn("lang", data)
        self.assertIs(build_quiz.validate_quiz(data), data)

    def test_good_lang_tags(self):
        for tag in ("ja", "en", "ko", "pt-BR", "zh-Hans-CN", "fil"):
            data = sample_quiz()
            data["lang"] = tag
            with self.subTest(tag=tag):
                self.assertIs(build_quiz.validate_quiz(data), data)

    def test_bad_lang_tags(self):
        for tag in ("", "j", "japanese", "en_US", "en-", "-en", "日本語", 1, None):
            data = sample_quiz()
            data["lang"] = tag
            with self.subTest(tag=tag), self.assertRaises(build_quiz.QuizError):
                build_quiz.validate_quiz(data)

    def test_ui_with_known_keys_passes(self):
        data = sample_quiz()
        data["lang"] = "ko"
        data["ui"] = {"submit": "제출", "meta": "총 {total}문항"}
        self.assertIs(build_quiz.validate_quiz(data), data)

    def test_ui_rejects_unknown_key_empty_value_and_non_object(self):
        cases = {
            "unknown key": {"sumbit": "Send"},
            "empty value": {"submit": ""},
            "blank value": {"submit": "  "},
            "non-string value": {"submit": 1},
        }
        for name, ui in cases.items():
            data = sample_quiz()
            data["ui"] = ui
            with self.subTest(case=name), self.assertRaises(build_quiz.QuizError):
                build_quiz.validate_quiz(data)
        for bad in ([], "submit", None):
            data = sample_quiz()
            data["ui"] = bad
            with self.subTest(ui=bad), self.assertRaises(build_quiz.QuizError):
                build_quiz.validate_quiz(data)

    def test_payload_defaults_to_japanese(self):
        payload = build_quiz.public_payload(sample_quiz())
        self.assertEqual(payload["lang"], "ja")
        self.assertEqual(payload["ui"], {})

    def test_payload_carries_lang_and_ui(self):
        data = sample_quiz()
        data["lang"] = "pt-BR"
        data["ui"] = {"submit": "Enviar"}
        payload = build_quiz.public_payload(data)
        self.assertEqual(payload["lang"], "pt-BR")
        self.assertEqual(payload["ui"], {"submit": "Enviar"})
        for q in payload["questions"]:
            self.assertEqual(set(q), {"no", "question", "choices"})

    def test_shuffle_keeps_lang_and_ui(self):
        data = sample_quiz()
        data["lang"] = "en"
        data["ui"] = {"submit": "Send answers"}
        shuffled = build_quiz.shuffle_choices(data, random.Random(0))
        self.assertEqual(shuffled["lang"], "en")
        self.assertEqual(shuffled["ui"], {"submit": "Send answers"})


def template_label_sets(template):
    """雛形の JS にある組み込みの文言表 LABELS から、言語ごとのキーの集合を取り出す。"""
    table = re.search(r"var LABELS = \{\n(.*?)\n  \};", template, re.S)
    if table is None:
        return {}
    sets = {}
    for lang, body in re.findall(r"^    (\w+): \{\n(.*?)\n    \}", table.group(1), re.S | re.M):
        sets[lang] = set(re.findall(r"^      (\w+): ", body, re.M))
    return sets


class TemplateLabelsTest(unittest.TestCase):
    """組み込みの ja と en の文言表が同じキーを持つことを確かめ、2 つの表がずれないように守る。
    build_quiz.UI_KEYS(ui で上書きできるキー)とも一致させる。"""

    def setUp(self):
        with open(TEMPLATE, encoding="utf-8") as f:
            self.template = f.read()

    def test_ja_and_en_have_the_same_keys(self):
        sets = template_label_sets(self.template)
        self.assertEqual(set(sets), {"ja", "en"})
        self.assertEqual(sets["ja"], sets["en"])
        self.assertEqual(sets["ja"], set(build_quiz.UI_KEYS))

    def test_japanese_wording_is_kept(self):
        for text in (
            "rikai 理解度チェック",
            "全 {total} 問。すべてに答えると提出できます。",
            "問{no}",
            "{answered} / {total} 問に回答",
            "提出する",
            "提出しました",
            "ターミナルに戻ると採点結果が出ます。このタブは閉じてかまいません。",
            "回答コードをターミナルに貼ってください",
            "下のコードをコピーして、ターミナルに貼り付けてください。",
            "コピーする",
            "コードを選択しました。コピーしてターミナルに貼り付けてください。",
            "回答コード",
        ):
            with self.subTest(text=text):
                self.assertIn("'" + text + "'", self.template)

    def test_template_sets_document_language(self):
        self.assertIn("document.documentElement.lang", self.template)

    def test_quiz_format_table_matches_the_built_in_labels(self):
        """quiz-format.md の文言表は雛形の組み込みの文言と一字一句同じにする。韓国語の例は全キーを持ち、検証を通る。"""
        with open(os.path.join(SKILL, "references", "quiz-format.md"), encoding="utf-8") as f:
            guide = f.read()
        section = guide.split("### 2.1", 1)[1].split("## 3.", 1)[0]
        rows = re.findall(r"^\| `(\w+)` \| (.+?) \| (.+?) \|$", section, re.M)
        self.assertEqual({key for key, _, _ in rows}, set(build_quiz.UI_KEYS))
        entries = set(re.findall(r"^      (\w+): '(.*)',?$", self.template, re.M))
        for key, ja, en in rows:
            with self.subTest(key=key):
                self.assertIn((key, ja), entries)
                self.assertIn((key, en), entries)
        example = re.search(r"```json\n(\"lang\": \"ko\",.*?)\n```", section, re.S).group(1)
        data = sample_quiz()
        data.update(json.loads("{" + example + "}"))
        build_quiz.validate_quiz(data)
        self.assertEqual(set(data["ui"]), set(build_quiz.UI_KEYS))


def many_questions(count):
    data = sample_quiz()
    template = data["questions"][0]
    data["questions"] = []
    for i in range(1, count + 1):
        q = copy.deepcopy(template)
        q["no"] = i
        q["topic_id"] = "topic-%03d" % i
        q["choices"] = [{"id": "a", "text": "正しい %d" % i}, {"id": "b", "text": "誤り %d-1" % i},
                        {"id": "c", "text": "誤り %d-2" % i}]
        q["correct"] = "a"
        data["questions"].append(q)
    return data


def correct_text(question):
    return next(c["text"] for c in question["choices"] if c["id"] == question["correct"])


class ShuffleTest(unittest.TestCase):
    def test_correct_text_is_kept_and_ids_are_reassigned(self):
        data = sample_quiz()
        before = copy.deepcopy(data)
        shuffled = build_quiz.shuffle_choices(data, random.Random(0))
        self.assertEqual(data, before)  # 元のデータは変えない
        build_quiz.validate_quiz(shuffled)
        for old, new in zip(before["questions"], shuffled["questions"]):
            self.assertEqual(correct_text(new), correct_text(old))
            self.assertEqual([c["id"] for c in new["choices"]], [chr(ord("a") + i) for i in range(len(new["choices"]))])
            self.assertEqual(sorted(c["text"] for c in new["choices"]), sorted(c["text"] for c in old["choices"]))
            self.assertEqual(new["topic_id"], old["topic_id"])

    def test_correct_position_varies(self):
        shuffled = build_quiz.shuffle_choices(many_questions(30), random.Random(0))
        self.assertGreaterEqual(len({q["correct"] for q in shuffled["questions"]}), 2)

    def test_default_rng_works(self):
        shuffled = build_quiz.shuffle_choices(many_questions(3))
        for q in shuffled["questions"]:
            self.assertTrue(correct_text(q).startswith("正しい"))


class QuestionOrderTest(unittest.TestCase):
    """問題の順番を無作為にする。選んだ順(復習問題が先)のまま出すと、どれが復習問題かが出題前に分かってしまう。"""

    def test_questions_are_reordered_and_renumbered(self):
        data = many_questions(12)
        shuffled = build_quiz.shuffle_questions(data, random.Random(1))
        build_quiz.validate_quiz(shuffled)
        self.assertEqual([q["no"] for q in shuffled["questions"]], list(range(1, 13)))
        before = [q["topic_id"] for q in data["questions"]]
        after = [q["topic_id"] for q in shuffled["questions"]]
        self.assertEqual(sorted(after), sorted(before))
        self.assertNotEqual(after, before)

    def test_each_question_keeps_its_own_content(self):
        data = many_questions(12)
        shuffled = build_quiz.shuffle_questions(data, random.Random(1))
        by_topic = {q["topic_id"]: q for q in data["questions"]}
        for q in shuffled["questions"]:
            original = dict(by_topic[q["topic_id"]])
            moved = dict(q)
            original.pop("no")
            moved.pop("no")
            self.assertEqual(moved, original)

    def test_original_data_is_not_modified(self):
        data = many_questions(12)
        snapshot = copy.deepcopy(data)
        build_quiz.shuffle_questions(data, random.Random(1))
        self.assertEqual(data, snapshot)

    def test_top_level_keys_are_kept(self):
        data = many_questions(3)
        data["lang"] = "en"
        shuffled = build_quiz.shuffle_questions(data, random.Random(1))
        self.assertEqual({k: v for k, v in shuffled.items() if k != "questions"},
                         {k: v for k, v in data.items() if k != "questions"})


class RenderTest(unittest.TestCase):
    def setUp(self):
        with open(TEMPLATE, encoding="utf-8") as f:
            self.template = f.read()

    def test_public_payload_hides_answers(self):
        text = json.dumps(build_quiz.public_payload(sample_quiz()), ensure_ascii=False)
        for hidden in ("correct", "topic_id", "topic-001", "aspect", "主張の識別"):
            self.assertNotIn(hidden, text)

    def test_topic_title_and_anchor_never_reach_the_form(self):
        data = sample_quiz()
        html = build_quiz.render_html(data, self.template)
        payload = embedded_payload(html)
        for q in payload["questions"]:
            self.assertEqual(set(q), {"no", "question", "choices"})
        for q in data["questions"]:
            for hidden in [q["title"], q["anchor"]["quote"]] + q["anchor"]["heading_path"]:
                self.assertNotIn(hidden, html)
        self.assertNotIn("anchor", json.dumps(payload))

    def test_html_survives_script_closing_tag_in_question(self):
        data = sample_quiz()
        nasty = "</script><b>太字</b> & <i>斜体</i> はどれですか。"
        data["questions"][0]["question"] = nasty
        html = build_quiz.render_html(data, self.template)
        self.assertNotIn("</script><b>", html)
        self.assertEqual(embedded_payload(html)["questions"][0]["question"], nasty)

    def test_line_separators_are_escaped_and_source_has_no_raw_ones(self):
        text = build_quiz.embed_json({"q": "a" + chr(0x2028) + "b" + chr(0x2029) + "c"})
        self.assertNotIn(chr(0x2028), text)
        self.assertNotIn(chr(0x2029), text)
        self.assertEqual(json.loads(text)["q"], "a" + chr(0x2028) + "b" + chr(0x2029) + "c")
        with open(build_quiz.__file__, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn(chr(0x2028), source)
        self.assertNotIn(chr(0x2029), source)

    def test_template_needs_exactly_one_placeholder(self):
        with self.assertRaises(build_quiz.QuizError):
            build_quiz.render_html(sample_quiz(), "<html></html>")

    def test_cli_writes_offline_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = os.path.join(tmp, "report.quiz.json")
            out_path = os.path.join(tmp, "report.quiz.html")
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(sample_quiz(), f, ensure_ascii=False)
            self.assertEqual(build_quiz.main(["--data", data_path, "--out", out_path, "--no-shuffle"]), 0)
            with open(out_path, encoding="utf-8") as f:
                html = f.read()
        self.assertEqual(len(embedded_payload(html)["questions"]), 2)
        self.assertIsNone(re.search(r'(src|href)\s*=\s*["\']https?://', html))
        self.assertNotIn("@import", html)

    def test_cli_reports_invalid_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = os.path.join(tmp, "bad.quiz.json")
            bad = copy.deepcopy(sample_quiz())
            bad["questions"][0]["correct"] = "z"
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(bad, f, ensure_ascii=False)
            out_path = os.path.join(tmp, "bad.quiz.html")
            with open(data_path, "rb") as f:
                original = f.read()
            self.assertEqual(build_quiz.main(["--data", data_path, "--out", out_path]), 1)
            self.assertFalse(os.path.exists(out_path))
            with open(data_path, "rb") as f:
                self.assertEqual(f.read(), original)  # 不正なデータは書き戻さない

    def test_cli_shuffles_and_writes_back_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = os.path.join(tmp, "report.quiz.json")
            out_path = os.path.join(tmp, "report.quiz.html")
            original = many_questions(12)
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(original, f, ensure_ascii=False)
            # 既定の乱数源を固定し、結果がぶれないようにする
            with mock.patch.object(build_quiz.random, "SystemRandom", lambda: random.Random(0)):
                self.assertEqual(build_quiz.main(["--data", data_path, "--out", out_path]), 0)
            with open(data_path, encoding="utf-8") as f:
                written = json.load(f)
            with open(out_path, encoding="utf-8") as f:
                payload = embedded_payload(f.read())
            self.assertEqual(sorted(os.listdir(tmp)), ["report.quiz.html", "report.quiz.json"])
        build_quiz.validate_quiz(written)
        self.assertEqual(payload, build_quiz.public_payload(written))
        by_topic = {q["topic_id"]: q for q in original["questions"]}
        for q in written["questions"]:
            self.assertEqual(correct_text(q), correct_text(by_topic[q["topic_id"]]))
        self.assertGreaterEqual(len({q["correct"] for q in written["questions"]}), 2)
        # 問題の順番も並べ替わり、番号は 1 から振り直される
        self.assertEqual([q["no"] for q in written["questions"]], list(range(1, 13)))
        self.assertNotEqual(
            [q["topic_id"] for q in written["questions"]], [q["topic_id"] for q in original["questions"]]
        )

    def test_cli_no_shuffle_leaves_data_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = os.path.join(tmp, "report.quiz.json")
            out_path = os.path.join(tmp, "report.quiz.html")
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(sample_quiz(), f, ensure_ascii=False)
            with open(data_path, "rb") as f:
                original = f.read()
            self.assertEqual(build_quiz.main(["--data", data_path, "--out", out_path, "--no-shuffle"]), 0)
            with open(data_path, "rb") as f:
                self.assertEqual(f.read(), original)
            with open(out_path, encoding="utf-8") as f:
                payload = embedded_payload(f.read())
        self.assertEqual(payload, build_quiz.public_payload(sample_quiz()))


if __name__ == "__main__":
    unittest.main()

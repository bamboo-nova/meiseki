import os
import re
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.join(REPO, ".agents", "skills", "rikai")
EXAMPLE = os.path.join(REPO, "examples", "rikai")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import build_dashboard as bd  # noqa: E402

EXTERNAL = re.compile(r'(?:(?:src|href)\s*=\s*["\']|url\(\s*["\']?)https?://|@import')


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def spec_example():
    """study-format.md §7 の正例(現行の形式の唯一の完全な例)をそのまま使う。"""
    fmt = read(os.path.join(SKILL, "references", "study-format.md"))
    return re.search(r"## 7\..*?```markdown\n(.*?)```", fmt, re.S).group(1)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class YamlSubsetTest(unittest.TestCase):
    def test_reads_the_spec_example_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sample-doc.study.md")
            write(path, spec_example())
            data = bd.validate_study(bd.read_frontmatter(path))
        self.assertEqual(data["schema_version"], 3)
        self.assertEqual(data["source_path"], "../sample-doc.md")
        ids = [t["id"] for t in data["topics"]]
        self.assertEqual(ids, ["topic-001", "topic-002", "topic-003", "topic-004"])
        t1 = data["topics"][0]
        self.assertEqual(t1["anchor"]["heading_path"], ["キャッシュ方針", "有効期限"])
        self.assertEqual(t1["anchor"]["line"], 12)
        self.assertIs(t1["attempts"][0]["correct"], False)
        self.assertEqual(t1["attempts"][0]["choices"][0], {"id": "1", "text": "5 分"})
        self.assertIsInstance(t1["attempts"][0]["user_answer"]["reasoning"], str)
        self.assertIsNone(t1["attempts"][1]["user_answer"]["reasoning"])
        manual = data["topics"][3]["manual_graduation"]
        self.assertEqual(manual["at"], "2026-10-19T20:00:00+09:00")
        self.assertIsInstance(manual["reason"], str)
        self.assertEqual(data["topics"][3]["attempts"], [])

    def test_reads_the_bundled_example(self):
        data = bd.validate_study(bd.read_frontmatter(os.path.join(EXAMPLE, ".rikai", "sample-doc.study.md")))
        self.assertEqual(len(data["topics"]), 8)
        self.assertEqual({t["status"] for t in data["topics"]}, set(bd.STATUSES))

    def test_scalars(self):
        self.assertEqual(
            bd.parse_yaml_subset('a: "x: y"\nb: \'it\'\'s\'\nc: null\nd: ~\ne:\nf: true\ng: -3\nh: []\ni: 007\n'),
            {"a": "x: y", "b": "it's", "c": None, "d": None, "e": None, "f": True, "g": -3, "h": [], "i": "007"},
        )

    def test_sequence_of_scalars_and_nested_maps(self):
        data = bd.parse_yaml_subset("k:\n  - a\n  - b: 1\n    c: 2\n  -\n    d: 3\nnext: x\n")
        self.assertEqual(data, {"k": ["a", {"b": 1, "c": 2}, {"d": 3}], "next": "x"})

    def test_sequence_at_the_same_indent_as_its_key(self):
        self.assertEqual(bd.parse_yaml_subset("k:\n- a\n- b\nz: 1\n"), {"k": ["a", "b"], "z": 1})

    def test_rejects_notation_outside_the_subset(self):
        for text in (
            "a: &x 1\nb: *x\n",          # アンカーとエイリアス
            "a: |\n  line\n",            # ブロックスカラー
            "a: [1, 2]\n",               # フロー形式
            "a: 今日は\n  続きの行\n",      # 複数行の plain スカラー
            "a:\n\tb: 1\n",              # タブ
            "a: 1\na: 2\n",              # キーの重複
            'a: "open\n',                # 閉じていない引用符
        ):
            with self.subTest(text=text):
                with self.assertRaises(bd.StudyFormatError):
                    bd.parse_yaml_subset(text)

    def test_frontmatter_must_be_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.study.md")
            write(path, "# 学習記録\n")
            with self.assertRaises(bd.StudyFormatError):
                bd.read_frontmatter(path)


class ValidationTest(unittest.TestCase):
    def topic(self, **over):
        t = {
            "id": "topic-001",
            "title": "t",
            "anchor": {"heading_path": ["h"], "quote": "q", "line": None},
            "status": "復習中",
            "attempts": [],
        }
        t.update(over)
        return t

    def test_rejects_bad_status_and_missing_keys(self):
        for bad in (
            {"schema_version": 4, "topics": []},
            {"schema_version": 3, "topics": [self.topic(status="done")]},
            {"schema_version": 3, "topics": [self.topic(anchor={"quote": "q"})]},
            {"schema_version": 3, "topics": [self.topic(attempts=[{"attempted_at": "x"}])]},
            {"schema_version": 3, "topics": [self.topic(manual_graduation={"reason": "r"})]},
            {"schema_version": 3, "topics": [self.topic(), self.topic()]},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(bd.StudyFormatError):
                    bd.validate_study(bad)

    def test_schema_1_without_title_falls_back_to_the_quote(self):
        t = self.topic(title=None, anchor={"heading_path": [], "quote": "原文の冒頭", "line": None})
        data = bd.validate_study({"schema_version": 1, "topics": [t]})
        self.assertEqual(bd.summarize_topics(data["topics"])["total"], 1)
        self.assertEqual(bd._title(t), "原文の冒頭")


class AggregationTest(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sample-doc.study.md")
            write(path, spec_example())
            self.topics = bd.validate_study(bd.read_frontmatter(path))["topics"]
        self.summary = bd.summarize_topics(self.topics)

    def test_counts_and_latest(self):
        self.assertEqual(self.summary["total"], 4)
        self.assertEqual(self.summary["counts"], {"復習中": 1, "卒業": 2, "要再抽出": 1})
        self.assertEqual(self.summary["attempted"], 3)
        self.assertEqual(self.summary["latest"], "2026-09-22T11:00:00+09:00")

    def test_misread_matches_the_feedback_report_order(self):
        """還流レポートと同じ順(誤答回数の降順 → 最終誤答日時の降順 → id の昇順)。"""
        self.assertEqual(
            [r["titles"] for r in self.summary["misread"]],
            [["更新後の購読者通知"], ["通常キャッシュの有効期限"], ["障害対応中の TTL 短縮"]],
        )
        self.assertEqual(self.summary["misread"][2]["heading_path"], ["キャッシュ方針", "例外"])
        self.assertEqual(sum(r["count"] for r in self.summary["misread"]), 3)

    def test_misread_groups_by_anchor_and_limits_to_five(self):
        topics = []
        for i in range(7):
            topics.append({
                "id": f"topic-{i:03d}",
                "title": f"t{i}",
                "anchor": {"heading_path": ["h"], "quote": "同じ段落" if i < 2 else f"q{i}", "line": None},
                "status": "復習中",
                "attempts": [{"attempted_at": f"2026-09-0{i + 1}T00:00:00+09:00", "correct": False}],
            })
        rows = bd.misread_paragraphs(topics)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["titles"], ["t0", "t1"])
        self.assertEqual(rows[0]["last"], "2026-09-02T00:00:00+09:00")
        self.assertEqual([r["count"] for r in rows[1:]], [1, 1, 1, 1])
        self.assertEqual(rows[1]["titles"], ["t6"])  # 同数なら最終誤答が新しい順

    def test_next_review_prefers_topics_whose_last_attempt_was_wrong(self):
        def t(tid, status, corrects):
            return {
                "id": tid,
                "title": tid,
                "anchor": {"heading_path": [], "quote": tid, "line": None},
                "status": status,
                "attempts": [
                    {"attempted_at": f"2026-09-0{i + 1}T00:00:00+09:00", "correct": c} for i, c in enumerate(corrects)
                ],
            }

        topics = [
            t("topic-001", "復習中", [False, True]),   # 誤答あり・前回は正解
            t("topic-002", "復習中", [True, False]),   # 誤答あり・前回は誤答
            t("topic-003", "復習中", []),              # 未挑戦は復習対象ではない
            t("topic-004", "卒業", [False, True, True, True]),
            t("topic-005", "復習中", [True]),          # 誤答なしの復習中(未保存の例外)は含めない
        ]
        self.assertEqual(bd.next_review(topics), ["topic-002", "topic-001"])

    def test_manual_graduations_are_listed_newest_first(self):
        self.assertEqual([m["title"] for m in self.summary["manual"]], ["監査ログの保持期間"])
        docs = [{"name": "a", "summary": self.summary, "error": None}, {"name": "b", "summary": self.summary, "error": None}]
        overall = bd.aggregate(docs)
        self.assertEqual([(m["document"], m["title"]) for m in overall["manual"]], [("a", "監査ログの保持期間"), ("b", "監査ログの保持期間")])
        self.assertEqual(overall["total"], 8)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.docs = os.path.join(self.tmp, "docs")
        self.rikai = os.path.join(self.docs, ".rikai")
        write(os.path.join(self.rikai, "sample-doc.study.md"), spec_example())
        shutil.copy(os.path.join(EXAMPLE, ".rikai", "sample-doc.study.md"), os.path.join(self.rikai, "worker.study.md"))
        write(os.path.join(self.rikai, "worker.explainer.html"), "<!doctype html><title>x</title>")
        write(os.path.join(self.rikai, "worker.explainer.tex"), "% manuscript")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def visible_text(self, html):
        text = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
        text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
        return re.sub(r"<[^>]+>", " ", text)

    def test_builds_a_self_contained_deterministic_page(self):
        out, docs = bd.build(rikai_dir=self.rikai)
        self.assertEqual(out, os.path.join(self.rikai, "dashboard.html"))
        self.assertEqual([d["name"] for d in docs], ["sample-doc", "worker"])
        html = read(out)
        self.assertIsNone(EXTERNAL.search(html))
        self.assertNotIn("{{", html)
        self.assertIsNone(re.search(r"topic-\d", self.visible_text(html)))
        self.assertIn('href="worker.explainer.html"', html)
        self.assertIn('href="worker.explainer.tex"', html)   # PDF がなければ原稿へ
        self.assertNotIn("worker.explainer.pdf", html)
        self.assertIn('href="sample-doc.study.md"', html)
        self.assertIn("監査ログの保持期間", html)
        self.assertIn("手動", html)
        self.assertEqual(html, read(bd.build(rikai_dir=self.rikai)[0]))

    def test_cards_carry_a_readable_record_per_topic(self):
        """生の study.md を開かなくても、論点ごとの状態と挑戦履歴が画面で読める。"""
        out, docs = bd.build(rikai_dir=self.rikai)
        html = read(out)
        records = docs[0]["summary"]["records"]
        self.assertEqual([r["title"] for r in records], ["通常キャッシュの有効期限", "障害対応中の TTL 短縮", "更新後の購読者通知", "監査ログの保持期間"])
        self.assertEqual((records[1]["correct"], records[1]["wrong"]), (3, 1))
        self.assertEqual([a["correct"] for a in records[1]["attempts"]], [True, False, True, True])
        self.assertIn("通常のキャッシュの有効期限はどれですか。", html)   # 問題文
        self.assertIn("具体例への適用", html)                              # 観点
        self.assertIn("2026-09-22 09:00", html)                            # 日時
        self.assertIn("正解 3・誤答 1", html)
        self.assertIn("未挑戦", html)
        self.assertIn("手動で卒業: 2026-10-19 20:00", html)
        self.assertIn("演習問題で繰り返し解いたため", html)
        self.assertIn("出題対象外です", html)
        self.assertIn('class="chip ok">卒業（手動）', html)
        self.assertEqual(html.count('<details class="record">'), 2)

    def test_accepts_the_parent_folder_and_explicit_out(self):
        out, _ = bd.build(rikai_dir=self.docs, out=os.path.join(self.tmp, "x", "d.html"))
        self.assertTrue(os.path.isfile(out))
        self.assertIn('href="../docs/.rikai/sample-doc.study.md"', read(out))

    def test_unreadable_study_md_is_reported_without_stopping(self):
        write(os.path.join(self.rikai, "broken.study.md"), "---\nschema_version: 3\ntopics:\n  - id: topic-001\n    status: done\n---\n")
        out, docs = bd.build(rikai_dir=self.rikai)
        broken = next(d for d in docs if d["name"] == "broken")
        self.assertIn("status", broken["error"])
        html = read(out)
        self.assertIn("読み取れませんでした", html)
        self.assertEqual(html.count('<article class="doc">'), 3)
        self.assertEqual(bd.main(["--rikai-dir", self.rikai]), 2)

    def test_root_mode_collects_nested_rikai_folders(self):
        other = os.path.join(self.tmp, "chapters", "ch2", ".rikai")
        write(os.path.join(other, "ch2.study.md"), spec_example())
        write(os.path.join(self.tmp, "node_modules", "pkg", ".rikai", "ignored.study.md"), spec_example())
        out, docs = bd.build(root=self.tmp, lang="en")
        self.assertEqual(out, os.path.join(self.tmp, ".rikai", "dashboard.html"))
        self.assertEqual([d["name"] for d in docs], ["chapters/ch2/ch2", "docs/sample-doc", "docs/worker"])
        html = read(out)
        self.assertIn("Learning progress dashboard", html)
        self.assertIn("Mastered", html)
        self.assertNotIn("復習中", self.visible_text(html))
        self.assertIn('href="../chapters/ch2/.rikai/ch2.study.md"', html)

    def test_cli_rejects_bad_arguments(self):
        self.assertEqual(bd.main(["--rikai-dir", os.path.join(self.tmp, "nowhere")]), 1)
        self.assertEqual(bd.main(["--rikai-dir", self.rikai, "--root", self.tmp]), 1)
        self.assertEqual(bd.main([]), 1)


class TemplateTest(unittest.TestCase):
    def test_template_loads_nothing_external_and_has_every_placeholder(self):
        html = read(os.path.join(SKILL, "assets", "dashboard-template.html"))
        self.assertIsNone(EXTERNAL.search(html))
        for key in (
            "{{LANG}}", "{{TITLE}}", "{{EYEBROW}}", "{{LEAD}}", "{{SUMMARY}}", "{{DOCS_HEADING}}", "{{DOCS}}",
            "{{MANUAL_HEADING}}", "{{MANUAL_LEAD}}", "{{MANUAL}}", "{{FOOTER}}",
        ):
            self.assertIn(key, html, key)

    def test_ui_tables_have_the_same_keys(self):
        self.assertEqual(set(bd.UI["ja"]), set(bd.UI["en"]))


if __name__ == "__main__":
    unittest.main()

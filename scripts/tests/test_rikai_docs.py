import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.join(REPO, ".agents", "skills", "rikai")
EXAMPLE = os.path.join(REPO, "examples", "rikai", ".rikai")
EXTERNAL = re.compile(r'(?:(?:src|href)\s*=\s*["\']|url\(\s*["\']?)https?://|@import')


def read(*parts):
    with open(os.path.join(SKILL, *parts), encoding="utf-8") as f:
        return f.read()


class TemplateTest(unittest.TestCase):
    def test_templates_load_nothing_external(self):
        for name in ("quiz-template.html", "explainer-template.html"):
            with self.subTest(name=name):
                self.assertIsNone(EXTERNAL.search(read("assets", name)))

    def test_explainer_template_has_markers_and_placeholders(self):
        html = read("assets", "explainer-template.html")
        for marker in (
            "<!-- rikai:progress:start -->",
            "<!-- rikai:progress:end -->",
            "<!-- rikai:topics:start -->",
            "<!-- rikai:topics:end -->",
        ):
            self.assertEqual(html.count(marker), 1, marker)
        self.assertEqual(html.count("{{SOURCE_NAME}}"), 3)
        self.assertEqual(html.count("{{UPDATED}}"), 1)

    def test_explainer_guide_uses_only_classes_the_template_defines(self):
        html = read("assets", "explainer-template.html")
        guide = read("references", "explainer-html.md")
        used = set()
        for value in re.findall(r'class="([^"]+)"', guide):
            used.update(value.split())
        missing = sorted(name for name in used if "." + name not in html)
        self.assertEqual(missing, [])


class SkillDocsTest(unittest.TestCase):
    def test_skill_has_no_retired_instructions(self):
        skill = read("SKILL.md")
        for retired in ("AskUserQuestion", "request_user_input", "なぜそう考えた", "ソクラテス", "mermaid", "jp-pdf", "ADR", "学習ノート", "バッチ"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, skill)

    def test_every_file_the_skill_mentions_exists(self):
        skill = read("SKILL.md")
        mentioned = set(re.findall(r"((?:references|scripts|assets)/[\w.-]+\.\w+)", skill))
        self.assertTrue(mentioned)
        for path in sorted(mentioned):
            with self.subTest(path=path):
                self.assertTrue(os.path.isfile(os.path.join(SKILL, path)), path)

    def test_skill_covers_every_script_and_reference(self):
        skill = read("SKILL.md")
        for name in (
            "scripts/build_quiz.py",
            "scripts/quiz_server.py",
            "scripts/build_textbook.py",
            "references/question-design.md",
            "references/study-format.md",
            "references/quiz-format.md",
            "references/explainer-html.md",
            "references/explainer-textbook.md",
        ):
            with self.subTest(name=name):
                self.assertIn(name, skill)

    def test_study_format_is_v3(self):
        fmt = read("references", "study-format.md")
        self.assertIn("現行値は `3`", fmt)
        self.assertIn("### 4.1 以前の形式からの移行", fmt)
        example = fmt.split("## 7.", 1)[1]  # 正例は現行の形式だけで書く
        self.assertIn("schema_version: 3", example)
        self.assertIn("# 学習記録", example)
        self.assertNotIn("# 学習ノート", example)
        self.assertNotIn("mermaid", example)
        self.assertNotIn("\n### ", example)

    def test_question_design_has_no_dialogue_section(self):
        design = read("references", "question-design.md")
        self.assertNotIn("誤答後の対話", design)
        self.assertNotIn("なぜそう考え", design)

    def test_session_files_are_deleted_right_after_saving(self):
        skill = read("SKILL.md")
        step5 = skill.split("### Step 5.", 1)[1].split("### Step 6.", 1)[0]
        step7 = skill.split("### Step 7.", 1)[1].split("## 5.", 1)[0]
        self.assertIn("すぐに出題データ、出題フォーム、回答ファイルを削除する", step5)
        for session_file in ("出題データ", "出題フォーム", "回答ファイル"):
            self.assertNotIn(session_file, step7)
        # Step 7 で削除に触れるのは、以前の方式の PDF を尋ねる 1 行だけ
        deleting = [line for line in step7.splitlines() if "削除" in line]
        self.assertEqual(len(deleting), 1)
        self.assertIn(".study.pdf", deleting[0])

    def test_resume_rules_guard_against_grading_twice(self):
        fmt = read("references", "quiz-format.md")
        section = fmt.split("## 5.", 1)[1]
        self.assertIn("同じ `session_id`", section)
        self.assertLess(section.index("同じ `session_id`"), section.index("| 出題データと回答がある |"))

    def test_python_is_not_required_for_the_text_route(self):
        skill = read("SKILL.md")
        step4 = skill.split("### Step 4.", 1)[1].split("### Step 5.", 1)[0]
        self.assertIn("`python3` がない環境では、下の表の優先 4 だけを使う", step4)
        row3 = next(line for line in step4.splitlines() if line.startswith("| 3 |"))
        self.assertNotIn("python3", row3)

    def test_text_route_presents_the_written_back_quiz_data(self):
        """テキストで出題する経路でも、build_quiz.py が書き戻した順と id で提示する(誤採点を防ぐ)。"""
        skill = read("SKILL.md")
        step4 = skill.split("### Step 4.", 1)[1].split("### Step 5.", 1)[0]
        row4 = next(line for line in step4.splitlines() if line.startswith("| 4 |"))
        self.assertIn("出題データを読み直し", row4)
        self.assertIn("テキストで提示するときは、その直前に出題データを読み直し、書かれている順と id のまま提示する。", step4)
        design = read("references", "question-design.md")
        section = design.split("## 5.", 1)[1].split("## 6.", 1)[0]
        self.assertIn("出題データを読み直し", section)

    def test_output_follows_the_users_language(self):
        skill = read("SKILL.md")
        self.assertNotIn("問い、選択肢、解説は日本語で書く", skill)
        self.assertNotIn("問いと解説は日本語で行う", skill)
        step3 = skill.split("### Step 3.", 1)[1].split("### Step 4.", 1)[0]
        self.assertIn("`lang`", step3)
        self.assertIn("references/quiz-format.md", step3)
        section2 = skill.split("## 2.", 1)[1].split("## 3.", 1)[0]
        self.assertIn("ユーザーの言語", section2)
        fmt = read("references", "study-format.md")
        self.assertIn("ユーザーの言語によらず", fmt)
        for name in ("explainer-html.md", "explainer-textbook.md"):
            with self.subTest(guide=name):
                self.assertRegex(read("references", name), r"\n## \d+\. 言語\n")

    def test_language_fallback_and_study_body(self):
        skill = read("SKILL.md")
        self.assertIn("依頼から言語を判断できない場合（ファイルのパスだけを渡された場合など）は、日本語を使う。", skill)
        fmt = read("references", "study-format.md")
        self.assertNotIn("ユーザーの言語によらず日本語で書く", fmt)
        self.assertIn("本文（導入と還流レポート）は、ユーザーの言語で書く", fmt)
        self.assertIn("Writer feedback report", fmt)

    def test_missing_script_characters_are_fixed_with_the_font(self):
        skill = read("SKILL.md")
        step6 = skill.split("### Step 6.", 1)[1].split("### Step 7.", 1)[0]
        self.assertIn("\\rikaifont", step6)

    def test_skill_forbids_installing_latex(self):
        self.assertIn("LaTeX を勝手にインストールしない", read("SKILL.md"))

    def test_session_id_has_seconds(self):
        skill = read("SKILL.md")
        step3 = skill.split("### Step 3.", 1)[1].split("### Step 4.", 1)[0]
        self.assertIn("`session-YYYYMMDD-HHMMSS`", step3)
        self.assertIn("出題対象が 1 つもなければ", step3)
        fmt = read("references", "quiz-format.md")
        self.assertIsNone(re.search(r'"session_id": "session-\d{8}-\d{2}"', fmt))
        self.assertRegex(fmt, r'"session_id": "session-\d{8}-\d{6}"')

    def test_the_script_places_the_correct_answer(self):
        skill = read("SKILL.md")
        step3 = skill.split("### Step 3.", 1)[1].split("### Step 4.", 1)[0]
        self.assertIn("scripts/build_quiz.py", step3)
        design = read("references", "question-design.md")
        section = design.split("## 5.", 1)[1].split("## 6.", 1)[0]
        self.assertIn("scripts/build_quiz.py", section)
        rule = next(line for line in section.splitlines() if "mod n" in line)
        self.assertIn("テキストだけで提示する場合", rule)

    def test_pasted_text_is_never_double_quoted(self):
        for parts in (("SKILL.md",), ("references", "quiz-format.md"), ("references", "explainer-textbook.md")):
            with self.subTest(doc=parts[-1]):
                text = read(*parts)
                self.assertIsNone(re.search(r'--(?:code|escape) "', text))
                self.assertIn("二重引用符に入れない", text)

    def test_quiz_data_carries_topic_title_and_anchor(self):
        fmt = read("references", "quiz-format.md")
        self.assertIn("| `questions[].title` |", fmt)
        self.assertIn("| `questions[].anchor` |", fmt)
        self.assertIn("study.md にまだない `topic_id` は、出題データの `title` と `anchor` から論点を復元してから採点する。", fmt)

    def test_explainers_follow_study_md(self):
        skill = read("SKILL.md")
        step6 = skill.split("### Step 6.", 1)[1].split("### Step 7.", 1)[0]
        self.assertIn("explainer を study.md に合わせる。", step6)
        for name in ("explainer-html.md", "explainer-textbook.md"):
            with self.subTest(guide=name):
                guide = read("references", name)
                self.assertIn("`要再抽出` の論点は", guide)
                self.assertIn("取り除く", guide)


def study_topics(path):
    """study.md の frontmatter から、論点 id ごとの状態と挑戦の有無を読む(PyYAML を使わない)。"""
    with open(path, encoding="utf-8") as f:
        front = f.read().split("---\n", 2)[1]
    topics = {}
    current = None
    for line in front.splitlines():
        m = re.match(r"^  - id: (topic-\d{3})$", line)
        if m:
            current = topics.setdefault(m.group(1), {"status": None, "attempted": False})
            continue
        if current is None:
            continue
        m = re.match(r"^    status: (\S+)$", line)
        if m:
            current["status"] = m.group(1)
        elif re.match(r"^      - attempted_at: ", line):
            current["attempted"] = True
    return topics


class ExampleTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(EXAMPLE, "sample-doc.explainer.html"), encoding="utf-8") as f:
            self.html = f.read()
        with open(os.path.join(EXAMPLE, "sample-doc.explainer.tex"), encoding="utf-8") as f:
            self.tex = f.read()
        self.topics = study_topics(os.path.join(EXAMPLE, "sample-doc.study.md"))

    def test_explainers_match_study_md(self):
        self.assertTrue(self.topics)
        expected = {
            tid for tid, t in self.topics.items() if t["attempted"] and t["status"] != "要再抽出"
        }
        html_ids = set(re.findall(r'<article class="q" id="(topic-\d{3})">', self.html))
        tex_ids = set(re.findall(r"^% >>> (topic-\d{3})$", self.tex, re.M))
        self.assertTrue(expected)
        self.assertEqual(html_ids, expected)
        self.assertEqual(tex_ids, expected)
        self.assertEqual(set(re.findall(r"^% <<< (topic-\d{3})$", self.tex, re.M)), expected)

    def test_html_is_self_contained_and_filled_in(self):
        self.assertIsNone(EXTERNAL.search(self.html))
        self.assertNotIn("{{", self.html)

    def test_topic_ids_are_not_shown_to_the_reader(self):
        visible = re.sub(r"<(script|style)\b.*?</\1>", " ", self.html, flags=re.S)
        visible = re.sub(r"<!--.*?-->", " ", visible, flags=re.S)
        spoken = re.findall(r'(?:aria-label|alt|title)="([^"]*)"', visible)
        visible = re.sub(r"<[^>]+>", " ", visible)
        self.assertIsNone(re.search(r"topic-\d", visible))
        for label in spoken:
            self.assertIsNone(re.search(r"topic-\d", label), label)


class QuestionOrderDocsTest(unittest.TestCase):
    """復習問題かどうかは、解く前には分からないようにする(順番は無作為、種別は採点後の表で伝える)。"""

    def test_skill_separates_selection_priority_from_presentation_order(self):
        skill = read("SKILL.md")
        step3 = skill.split("### Step 3.", 1)[1].split("### Step 4.", 1)[0]
        self.assertIn("出題する順ではない", step3)
        self.assertIn("無作為に並べ替える", step3)
        self.assertNotIn("先頭に置く", step3)

    def test_result_table_reveals_review_questions(self):
        skill = read("SKILL.md")
        step5 = skill.split("### Step 5.", 1)[1].split("### Step 6.", 1)[0]
        self.assertIn("種別", step5)
        self.assertIn("「復習」", step5)

    def test_references_say_the_script_reorders_questions(self):
        self.assertIn("問題の順番を無作為に並べ替え", read("references", "quiz-format.md"))
        self.assertIn("問題の順番は無作為にする", read("references", "question-design.md"))


if __name__ == "__main__":
    unittest.main()

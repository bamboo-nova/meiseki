import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.join(REPO, ".agents", "skills", "rikai")
STY = os.path.join(SKILL, "assets", "rikai-textbook.sty")
GUIDE = os.path.join(SKILL, "references", "explainer-textbook.md")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import build_textbook  # noqa: E402


def has_toolchain():
    return shutil.which("xelatex") is not None


SAMPLE = r"""\documentclass[10pt]{article}
\usepackage{rikai-textbook}
\begin{document}
\rikaititle{report\_v2 \& notes.md}{2026-10-04}
\tableofcontents
\section{4.2 損失の見積もり}
% >>> topic-020
\topic{SLE と ALE の計算式}{復習中}
1 回の損失額と、1 年あたりの損失額を分けて考える。
\begin{youten}
\begin{equation}
  \mathrm{SLE} = \mathrm{AV} \times \mathrm{EF}, \qquad \mathrm{ALE} = \mathrm{SLE} \times \mathrm{ARO}
\end{equation}
\end{youten}
\begin{reidai}[サーバの火災]
\begin{align}
  \mathrm{SLE} &= 1{,}000 \times 0.6 = 600 \text{ 万円} \\
  \mathrm{ALE} &= 600 \times 0.1 = 60 \text{ 万円/年}
\end{align}
\end{reidai}
\begin{mayoi}
EF は資産に固定の値ではない。
\end{mayoi}
\begin{genbun}
「SLE = AV x EF」
\end{genbun}
\begin{center}
\begin{tikzpicture}[node distance=14mm]
  \node[draw] (a) {AV};
  \node[draw,right=of a] (b) {SLE};
  \draw[-{Stealth}] (a) -- node[above] {\small $\times$ EF} (b);
\end{tikzpicture}
\end{center}
% <<< topic-020
\end{document}
"""


LABELS_EN = {
    "rikaiLabelPoint": "Key point",
    "rikaiLabelExample": "Example",
    "rikaiLabelPitfall": "Where it gets confusing",
    "rikaiLabelSource": "Source",
    "rikaiLabelToc": "Contents",
    "rikaiLabelBook": "Textbook",
    "rikaiLabelUpdated": "Last updated",
    "rikaiLabelStatus": "Status",
    "rikaiLabelStatusSep": ": ",
    "rikaiLabelDisclaimer": "Facts are based on the source text. Some numbers, names and situations in the examples were added for explanation.",
}

SAMPLE_EN = (
    "\\documentclass[10pt]{article}\n\\usepackage{rikai-textbook}\n"
    + "".join("\\renewcommand{\\%s}{%s}\n" % item for item in LABELS_EN.items())
    + r"""\begin{document}
\rikaititle{report\_v2 \& notes.md}{October 4, 2026}
\tableofcontents
\section{4.2 Estimating losses}
% >>> topic-020
\topic{The SLE and ALE formulas}{Reviewing}
Estimate the loss per incident and the loss per year separately.
\begin{youten}
\begin{equation}
  \mathrm{SLE} = \mathrm{AV} \times \mathrm{EF}, \qquad \mathrm{ALE} = \mathrm{SLE} \times \mathrm{ARO}
\end{equation}
\end{youten}
\begin{reidai}[A fire in the server room (for illustration)]
\begin{align}
  \mathrm{SLE} &= 1{,}000 \times 0.6 = 600 \\
  \mathrm{ALE} &= 600 \times 0.1 = 60 \text{ per year}
\end{align}
\end{reidai}
\begin{mayoi}
EF is not a fixed property of the asset.
\end{mayoi}
\begin{genbun}
"SLE = AV x EF"
\end{genbun}
% <<< topic-020
\end{document}
"""
)


class EscapeTest(unittest.TestCase):
    def test_special_characters(self):
        self.assertEqual(
            build_textbook.tex_escape("report_v2 & 50% #1 $x$ {a}"),
            r"report\_v2 \& 50\% \#1 \$x\$ \{a\}",
        )

    def test_backslash_tilde_caret(self):
        self.assertEqual(
            build_textbook.tex_escape("a\\b~c^d"),
            r"a\textbackslash{}b\textasciitilde{}c\textasciicircum{}d",
        )

    def test_cli_escape(self):
        self.assertEqual(build_textbook.main(["--escape", "a_b"]), 0)

    def test_cli_escape_reads_stdin_with_dash(self):
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO("$HOME & `id`.md\n")), contextlib.redirect_stdout(stdout):
            self.assertEqual(build_textbook.main(["--escape", "-"]), 0)
        self.assertEqual(stdout.getvalue(), "\\$HOME \\& `id`.md\n")

    def test_cli_escape_strips_only_one_trailing_newline(self):
        stdout = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO("a_b\n\n")), contextlib.redirect_stdout(stdout):
            build_textbook.main(["--escape", "-"])
        self.assertEqual(stdout.getvalue(), "a\\_b\n\n")


class InstallHintTest(unittest.TestCase):
    def test_macos(self):
        self.assertTrue(any("mactex" in line for line in build_textbook.install_hint("Darwin")))

    def test_windows(self):
        self.assertTrue(any("install-tl-windows" in line for line in build_textbook.install_hint("Windows")))

    def test_unknown_system_points_to_tex_live(self):
        self.assertTrue(any("tug.org/texlive" in line for line in build_textbook.install_hint("Plan9")))


class SummarizeLogTest(unittest.TestCase):
    def test_file_line_error_with_context(self):
        log = "\n".join([
            "(./main.tex",
            "./main.tex:12: Undefined control sequence.",
            "l.12 \\foo",
            "         bar",
            "! Emergency stop.",
        ])
        self.assertEqual(
            build_textbook.summarize_log(log),
            ["12 行目: Undefined control sequence. ／ l.12 \\foo"],
        )

    def test_error_inside_style_file_names_the_file(self):
        log = './rikai-textbook.sty:9: Package fontspec Error: The font "IPAexGothic" cannot be found.'
        result = build_textbook.summarize_log(log)
        self.assertIn("rikai-textbook.sty 9 行目", result[0])
        self.assertTrue(any("日本語フォント" in entry for entry in result))

    def test_bang_errors_without_location(self):
        log = "! LaTeX Error: File `nothing.sty' not found.\n! Emergency stop."
        self.assertEqual(build_textbook.summarize_log(log), ["LaTeX Error: File `nothing.sty' not found."])

    def test_limit(self):
        log = "\n".join(f"./main.tex:{n}: Undefined control sequence." for n in range(1, 10))
        self.assertEqual(len(build_textbook.summarize_log(log, limit=3)), 3)


class MissingCharactersTest(unittest.TestCase):
    def test_unique_characters_in_order(self):
        log = "\n".join([
            "Missing character: There is no " + chr(0x2460) + " (U+2460) in font [lmroman10-regular]:mapping=tex-text;!",
            "Some other line",
            "Missing character: There is no " + chr(0x1F600) + " (U+1F600) in font IPAexGothic:mode=harf;!",
            "Missing character: There is no " + chr(0x2460) + " (U+2460) in font [lmroman10-bold]:mapping=tex-text;!",
        ])
        self.assertEqual(build_textbook.missing_characters(log), [chr(0x2460), chr(0x1F600)])

    def test_no_missing_characters(self):
        self.assertEqual(build_textbook.missing_characters("Output written on main.pdf (1 page)."), [])


class StyleTest(unittest.TestCase):
    def setUp(self):
        with open(STY, encoding="utf-8") as f:
            self.sty = f.read()

    def test_everything_the_guide_uses_is_defined(self):
        with open(GUIDE, encoding="utf-8") as f:
            guide = f.read()
        standard = {"document", "equation", "align", "tabular", "center", "tikzpicture"}
        used = set(re.findall(r"\\begin\{(\w+)\}", guide)) | set(re.findall(r"`(\w+)` 環境", guide))
        used -= standard
        self.assertTrue({"youten", "reidai", "mayoi", "genbun"} <= used)
        for env in sorted(used | {"youten", "reidai", "mayoi", "genbun"}):
            with self.subTest(environment=env):
                self.assertRegex(self.sty, r"\\newtcolorbox(\[[^\]]*\])?\{" + env + r"\}")
        for command in ("rikaititle", "topic"):
            with self.subTest(command=command):
                self.assertIn("\\" + command, guide)
                self.assertIn("\\newcommand{\\" + command + "}", self.sty)
        self.assertIn("L{", guide)
        self.assertIn("\\newcolumntype{L}", self.sty)

    def test_sections_are_not_numbered_and_examples_count_through_the_document(self):
        self.assertIn("\\setcounter{secnumdepth}{0}", self.sty)
        self.assertNotIn("number within", self.sty)
        self.assertIn("\\newtcolorbox[auto counter]{reidai}", self.sty)

    def test_symbols_go_to_the_japanese_font(self):
        after = self.sty.split("\\RequirePackage{xeCJK}", 1)[1]
        self.assertTrue(after.lstrip().startswith("\\xeCJKDeclareCharClass{CJK}"))

    def test_every_label_macro_the_guide_lists_is_defined(self):
        with open(GUIDE, encoding="utf-8") as f:
            guide = f.read()
        listed = set(re.findall(r"\\(rikaiLabel[A-Za-z]+)", guide))
        self.assertEqual(listed, set(LABELS_EN))
        for name in sorted(listed):
            with self.subTest(macro=name):
                self.assertRegex(self.sty, r"\\newcommand\{\\" + name + r"\}\{")
                # 固定の文字列は sty の中でマクロを通して使う
                self.assertGreaterEqual(self.sty.count("\\" + name), 2)

    def test_guide_escape_table_matches_the_script(self):
        """python3 がないときに手でエスケープできるよう、ガイドの表はスクリプトと同じ対応を載せる。"""
        with open(GUIDE, encoding="utf-8") as f:
            guide = f.read()
        rows = dict(re.findall(r"^\| `(.)` \| `([^`]+)` \|$", guide, re.M))
        self.assertEqual(rows, build_textbook.ESCAPES)

    def test_title_carries_the_disclaimer(self):
        self.assertIn("事実の根拠は資料の原文です。例題の数値・名前・場面には、説明のために足したものがあります。", self.sty)


class BuildTest(unittest.TestCase):
    def test_missing_xelatex_returns_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "report.explainer.tex")
            out = os.path.join(tmp, "report.explainer.pdf")
            with open(src, "w", encoding="utf-8") as f:
                f.write(SAMPLE)
            stderr = io.StringIO()
            with mock.patch("build_textbook.shutil.which", return_value=None), contextlib.redirect_stderr(stderr):
                self.assertEqual(build_textbook.build(src, out), 3)
            self.assertFalse(os.path.exists(out))
            self.assertTrue("tug.org" in stderr.getvalue() or "mactex" in stderr.getvalue())

    def test_timeout_returns_1_with_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "report.explainer.tex")
            out = os.path.join(tmp, "report.explainer.pdf")
            with open(src, "w", encoding="utf-8") as f:
                f.write(SAMPLE)
            stderr = io.StringIO()
            hang = subprocess.TimeoutExpired(cmd="xelatex", timeout=300)
            with mock.patch("build_textbook.shutil.which", return_value="/usr/bin/xelatex"), \
                    mock.patch("build_textbook.subprocess.run", side_effect=hang) as run, \
                    contextlib.redirect_stderr(stderr):
                self.assertEqual(build_textbook.build(src, out), 1)
            self.assertIn("[build_textbook] コンパイルが 300 秒で終わりませんでした", stderr.getvalue())
            self.assertFalse(os.path.exists(out))
            kwargs = run.call_args.kwargs
            self.assertEqual(kwargs["timeout"], 300)
            self.assertIs(kwargs["stdin"], subprocess.DEVNULL)

    def test_missing_input_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = build_textbook.main(
                ["--input", os.path.join(tmp, "none.tex"), "--output", os.path.join(tmp, "none.pdf")]
            )
            self.assertEqual(code, 1)

    @unittest.skipUnless(has_toolchain(), "xelatex が必要")
    def test_builds_pdf_and_leaves_no_intermediate_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "report.explainer.tex")
            out = os.path.join(tmp, "report.explainer.pdf")
            with open(src, "w", encoding="utf-8") as f:
                f.write(SAMPLE)
            self.assertEqual(build_textbook.build(src, out), 0)
            with open(out, "rb") as f:
                self.assertEqual(f.read(4), b"%PDF")
            self.assertEqual(sorted(os.listdir(tmp)), ["report.explainer.pdf", "report.explainer.tex"])

    @unittest.skipUnless(has_toolchain(), "xelatex が必要")
    def test_english_labels_build_without_missing_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "report.explainer.tex")
            out = os.path.join(tmp, "report.explainer.pdf")
            with open(src, "w", encoding="utf-8") as f:
                f.write(SAMPLE_EN)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build_textbook.build(src, out), 0, stderr.getvalue())
            with open(out, "rb") as f:
                self.assertEqual(f.read(4), b"%PDF")
        self.assertNotIn("警告", stderr.getvalue())

    @unittest.skipUnless(has_toolchain(), "xelatex が必要")
    def test_symbols_and_greek_build_without_missing_characters(self):
        # ≤ ≥ (U+2264, U+2265) は IPAexGothic にもないので含めない。ガイドの指示どおり $\le$ で書く
        body = (
            "記号 " + "".join(chr(c) for c in (0x2460, 0x2461, 0x25CF, 0x25A0, 0x2605, 0x21D2, 0x2266, 0x2267,
                                              0x2713, 0x03B1, 0x03B2, 0x2015, 0x2192, 0x2500))
            + " と数式 $\\alpha + \\beta \\le \\gamma$。\n"
            "\\begin{tabular}{lL{0.6}}\n項目 & 文が入る列 \\\\\n\\end{tabular}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "report.explainer.tex")
            out = os.path.join(tmp, "report.explainer.pdf")
            with open(src, "w", encoding="utf-8") as f:
                f.write(SAMPLE.replace("% <<< topic-020", body + "% <<< topic-020"))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build_textbook.build(src, out), 0)
            self.assertNotIn("警告", stderr.getvalue())

    @unittest.skipUnless(has_toolchain(), "xelatex が必要")
    def test_emoji_builds_with_a_warning(self):
        emoji = chr(0x1F600)
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "report.explainer.tex")
            out = os.path.join(tmp, "report.explainer.pdf")
            with open(src, "w", encoding="utf-8") as f:
                f.write(SAMPLE.replace("1 回の損失額と", emoji + " 1 回の損失額と"))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(build_textbook.build(src, out), 0)
            self.assertTrue(os.path.exists(out))
        text = stderr.getvalue()
        self.assertIn("[build_textbook] 警告: 次の文字はフォントになく、PDF に出ていません: " + emoji, text)
        self.assertIn("  原稿でほかの書き方に置き換えて、もう一度ビルドしてください", text)

    @unittest.skipUnless(has_toolchain(), "xelatex が必要")
    def test_compile_error_returns_1_and_keeps_old_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "report.explainer.tex")
            out = os.path.join(tmp, "report.explainer.pdf")
            with open(out, "wb") as f:
                f.write(b"%PDF-old")
            with open(src, "w", encoding="utf-8") as f:
                f.write(SAMPLE.replace("1 回の損失額と", "\\undefinedmacro 1 回の損失額と"))
            self.assertEqual(build_textbook.build(src, out), 1)
            with open(out, "rb") as f:
                self.assertEqual(f.read(), b"%PDF-old")


class RerunTest(unittest.TestCase):
    """目次と相互参照が落ち着くまでコンパイルを繰り返す。

    回数を 2 回に固定すると、目次が 2 ページ以上になる原稿で、目次のページ番号がずれたまま終わる。
    """

    def run_with_fake_xelatex(self, toc_for_call, **kwargs):
        calls = []

        def fake_run(cmd, cwd=None, **_):
            calls.append(1)
            with open(os.path.join(cwd, "main.toc"), "w", encoding="utf-8") as f:
                f.write(toc_for_call(len(calls)))
            with open(os.path.join(cwd, "main.aux"), "w", encoding="utf-8") as f:
                f.write("aux")
            with open(os.path.join(cwd, "main.log"), "w", encoding="utf-8") as f:
                f.write("")
            with open(os.path.join(cwd, "main.pdf"), "wb") as f:
                f.write(b"%PDF-fake")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a.explainer.tex")
            out = os.path.join(tmp, "a.explainer.pdf")
            with open(src, "w", encoding="utf-8") as f:
                f.write("x")
            with mock.patch("build_textbook.shutil.which", return_value="/usr/bin/xelatex"), \
                    mock.patch("build_textbook.subprocess.run", side_effect=fake_run), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = build_textbook.build(src, out, **kwargs)
        return code, len(calls)

    def test_reruns_until_the_table_of_contents_stops_changing(self):
        code, calls = self.run_with_fake_xelatex(lambda n: "pass %d" % min(n, 3))
        self.assertEqual(code, 0)
        self.assertEqual(calls, 4)  # 3 回目で落ち着き、4 回目で変化なしを確かめて止まる

    def test_a_stable_document_takes_two_runs(self):
        code, calls = self.run_with_fake_xelatex(lambda n: "same")
        self.assertEqual(code, 0)
        self.assertEqual(calls, 2)

    def test_stops_at_the_maximum_number_of_runs(self):
        code, calls = self.run_with_fake_xelatex(lambda n: "pass %d" % n)
        self.assertEqual(code, 0)
        self.assertEqual(calls, build_textbook.MAX_RUNS)

    def test_runs_argument_caps_the_number_of_runs(self):
        code, calls = self.run_with_fake_xelatex(lambda n: "pass %d" % n, runs=3)
        self.assertEqual(code, 0)
        self.assertEqual(calls, 3)


if __name__ == "__main__":
    unittest.main()

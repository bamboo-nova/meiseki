import contextlib
import http.client
import io
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.join(REPO, ".agents", "skills", "rikai")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import build_quiz  # noqa: E402
import quiz_server  # noqa: E402

QUIZ = {
    "format": 1,
    "session_id": "session-test-01",
    "title": "report.md の理解度チェック",
    "questions": [
        {
            "no": 1, "topic_id": "topic-001", "title": "論点 1",
            "anchor": {"heading_path": ["1. 概要"], "quote": "原文 1", "line": 3},
            "aspect": "主張の識別", "question": "問い 1",
            "choices": [{"id": "a", "text": "ア"}, {"id": "b", "text": "イ"}, {"id": "c", "text": "ウ"}],
            "correct": "b",
        },
        {
            "no": 2, "topic_id": "topic-002", "title": "論点 2",
            "anchor": {"heading_path": ["1. 概要"], "quote": "原文 2", "line": None},
            "aspect": "例外条件", "question": "問い 2",
            "choices": [{"id": "a", "text": "ア"}, {"id": "b", "text": "イ"}],
            "correct": "a",
        },
    ],
}


class AnswerCodeTest(unittest.TestCase):
    def test_plain_code(self):
        self.assertEqual(quiz_server.parse_answer_code("1:b 2:a"), {"1": "b", "2": "a"})

    def test_fullwidth_newline_and_comma(self):
        self.assertEqual(
            quiz_server.parse_answer_code("１：Ｂ\n２：ａ、 3:C,"),
            {"1": "b", "2": "a", "3": "c"},
        )

    def test_leading_zero_is_normalized(self):
        self.assertEqual(quiz_server.parse_answer_code("01:a"), {"1": "a"})

    def test_duplicate_question_rejected(self):
        with self.assertRaises(quiz_server.AnswerError):
            quiz_server.parse_answer_code("1:a 1:b")

    def test_unreadable_code_rejected(self):
        with self.assertRaises(quiz_server.AnswerError):
            quiz_server.parse_answer_code("わかりません")


class ValidateAnswersTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(quiz_server.validate_answers(QUIZ, {"1": "b", 2: "a"}), {"1": "b", "2": "a"})

    def test_missing_question(self):
        with self.assertRaises(quiz_server.AnswerError):
            quiz_server.validate_answers(QUIZ, {"1": "b"})

    def test_unknown_choice(self):
        with self.assertRaises(quiz_server.AnswerError):
            quiz_server.validate_answers(QUIZ, {"1": "z", "2": "a"})

    def test_extra_question(self):
        with self.assertRaises(quiz_server.AnswerError):
            quiz_server.validate_answers(QUIZ, {"1": "b", "2": "a", "3": "a"})


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "report.quiz.json")
        self.html = os.path.join(self.tmp.name, "report.quiz.html")
        self.out = os.path.join(self.tmp.name, "report.answers.json")
        with open(self.data, "w", encoding="utf-8") as f:
            json.dump(QUIZ, f, ensure_ascii=False)
        with open(os.path.join(SKILL, "assets", "quiz-template.html"), encoding="utf-8") as f:
            template = f.read()
        with open(self.html, "w", encoding="utf-8") as f:
            f.write(build_quiz.render_html(QUIZ, template))

    def start(self, timeout=10):
        ready = threading.Event()
        box = {}

        def on_ready(url):
            box["url"] = url
            ready.set()

        def run():
            box["code"] = quiz_server.serve(
                self.html, self.data, self.out, timeout=timeout, open_browser=False, on_ready=on_ready
            )

        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(ready.wait(5))
        return thread, box

    def request(self, url, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def submit_url(self, url):
        return url.replace("/?t=", "/submit?t=")

    def good_body(self):
        return {"session_id": "session-test-01", "answers": {"1": "b", "2": "a"}}

    def finish(self, thread, box):
        self.request(self.submit_url(box["url"]), self.good_body())
        thread.join(5)

    def test_get_serves_form_only_with_token(self):
        thread, box = self.start()
        status, body = self.request(box["url"])
        self.assertEqual(status, 200)
        self.assertIn('id="quiz-data"', body)
        status, _ = self.request(box["url"].split("?")[0])
        self.assertEqual(status, 403)
        self.finish(thread, box)

    def test_submit_writes_answers_and_stops(self):
        thread, box = self.start()
        status, _ = self.request(self.submit_url(box["url"]), self.good_body())
        self.assertEqual(status, 200)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(box["code"], 0)
        with open(self.out, encoding="utf-8") as f:
            record = json.load(f)
        self.assertEqual(record["answers"], {"1": "b", "2": "a"})
        self.assertEqual(record["via"], "server")
        self.assertEqual(record["session_id"], "session-test-01")

    def test_incomplete_submission_keeps_waiting(self):
        thread, box = self.start()
        status, _ = self.request(
            self.submit_url(box["url"]), {"session_id": "session-test-01", "answers": {"1": "b"}}
        )
        self.assertEqual(status, 400)
        self.assertFalse(os.path.exists(self.out))
        self.assertTrue(thread.is_alive())
        self.finish(thread, box)
        self.assertEqual(box["code"], 0)

    def test_stale_tab_from_another_session_is_rejected(self):
        thread, box = self.start()
        status, _ = self.request(
            self.submit_url(box["url"]), {"session_id": "session-old", "answers": {"1": "b", "2": "a"}}
        )
        self.assertEqual(status, 400)
        self.assertFalse(os.path.exists(self.out))
        self.finish(thread, box)

    def test_wrong_token_is_forbidden(self):
        thread, box = self.start()
        bad = self.submit_url(box["url"]).split("?")[0] + "?t=wrong"
        status, _ = self.request(bad, self.good_body())
        self.assertEqual(status, 403)
        self.assertFalse(os.path.exists(self.out))
        self.finish(thread, box)

    def test_concurrent_submissions_accept_exactly_one(self):
        entered = threading.Event()
        release = threading.Event()
        real_write = quiz_server.write_answers

        def slow_write(*args, **kwargs):
            entered.set()
            release.wait(5)
            return real_write(*args, **kwargs)

        thread, box = self.start()
        url = self.submit_url(box["url"])
        bodies = {
            "A": {"session_id": "session-test-01", "answers": {"1": "b", "2": "a"}},
            "B": {"session_id": "session-test-01", "answers": {"1": "a", "2": "b"}},
        }
        statuses = {}

        def post(label):
            statuses[label] = self.request(url, bodies[label])[0]

        with mock.patch.object(quiz_server, "write_answers", side_effect=slow_write):
            a = threading.Thread(target=post, args=("A",))
            a.start()
            self.assertTrue(entered.wait(5))  # A がロックを持ったまま書き込み中
            b = threading.Thread(target=post, args=("B",))
            b.start()
            time.sleep(0.3)  # B がロックで待つ時間を与える
            release.set()
            a.join(5)
            b.join(5)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(statuses.values()), [200, 409])
        winner = "A" if statuses["A"] == 200 else "B"
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["answers"], bodies[winner]["answers"])

    def test_write_failure_returns_500_and_keeps_waiting(self):
        thread, box = self.start()
        url = self.submit_url(box["url"])
        stderr = io.StringIO()
        with mock.patch.object(quiz_server, "write_answers", side_effect=OSError("disk full")):
            with contextlib.redirect_stderr(stderr):
                status, body = self.request(url, self.good_body())
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body), {"ok": False, "error": "回答を保存できませんでした"})
        self.assertIn("[quiz_server] 回答を保存できませんでした: disk full", stderr.getvalue())
        self.assertFalse(os.path.exists(self.out))
        self.assertTrue(thread.is_alive())
        status, _ = self.request(url, self.good_body())
        self.assertEqual(status, 200)
        thread.join(5)
        self.assertEqual(box["code"], 0)
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["answers"], {"1": "b", "2": "a"})

    def test_non_ascii_token_is_forbidden(self):
        thread, box = self.start()
        status, _ = self.request(box["url"].split("?")[0] + "?t=%E3%81%82")
        self.assertEqual(status, 403)
        self.finish(thread, box)

    def test_serve_command_rejects_missing_output_directory(self):
        out = os.path.join(self.tmp.name, "no-such-dir", "report.answers.json")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = quiz_server.main(
                ["serve", "--quiz", self.html, "--data", self.data, "--out", out, "--no-open", "--timeout", "2"]
            )
        self.assertEqual(code, 1)
        self.assertIn("no-such-dir", stderr.getvalue())

    def test_timeout_returns_2(self):
        thread, box = self.start(timeout=0.3)
        thread.join(5)
        self.assertEqual(box["code"], 2)
        self.assertFalse(os.path.exists(self.out))

    def raw(self, url, method="GET", body=None, headers=None):
        """urllib を通さずに要求を送る。Host や Content-Length を任意の値にできる。"""
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
        try:
            conn.putrequest(method, parsed.path + ("?" + parsed.query if parsed.query else ""), skip_host=True)
            sent = {"Host": "%s:%d" % (parsed.hostname, parsed.port)}
            if body is not None:
                sent["Content-Type"] = "application/json"
                sent["Content-Length"] = str(len(body))
            sent.update(headers or {})
            for key, value in sent.items():
                conn.putheader(key, value)
            conn.endheaders()
            if body is not None:
                conn.send(body)
            response = conn.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            conn.close()

    def test_foreign_host_header_is_forbidden(self):
        thread, box = self.start()
        good = json.dumps(self.good_body()).encode("utf-8")
        for host in ("evil.example", "evil.example:80", "127.0.0.1.evil.example"):
            with self.subTest(host=host):
                status, _ = self.raw(box["url"], headers={"Host": host})
                self.assertEqual(status, 403)
                status, _ = self.raw(self.submit_url(box["url"]), "POST", good, {"Host": host})
                self.assertEqual(status, 403)
        self.assertFalse(os.path.exists(self.out))
        self.finish(thread, box)

    def test_localhost_host_header_is_accepted(self):
        thread, box = self.start()
        port = urllib.parse.urlparse(box["url"]).port
        status, _ = self.raw(box["url"], headers={"Host": "localhost:%d" % port})
        self.assertEqual(status, 200)
        self.finish(thread, box)

    def test_oversized_body_is_rejected(self):
        thread, box = self.start()
        status, _ = self.raw(
            self.submit_url(box["url"]), "POST", b"{}",
            {"Content-Length": str(quiz_server.MAX_BODY + 1)},
        )
        self.assertEqual(status, 400)
        self.assertFalse(os.path.exists(self.out))
        self.assertTrue(thread.is_alive())
        self.finish(thread, box)

    def test_malformed_and_non_object_bodies_are_rejected(self):
        thread, box = self.start()
        for body in (b"{not json", b"[1, 2]", b'"text"', b"\xff\xfe"):
            with self.subTest(body=body):
                status, _ = self.raw(self.submit_url(box["url"]), "POST", body)
                self.assertEqual(status, 400)
        self.assertFalse(os.path.exists(self.out))
        self.assertTrue(thread.is_alive())
        self.finish(thread, box)

    def test_unknown_path_is_404(self):
        thread, box = self.start()
        token = box["url"].split("?", 1)[1]
        base = box["url"].split("/?", 1)[0]
        status, _ = self.raw(base + "/other?" + token)
        self.assertEqual(status, 404)
        status, _ = self.raw(base + "/other?" + token, "POST", json.dumps(self.good_body()).encode("utf-8"))
        self.assertEqual(status, 404)
        self.assertFalse(os.path.exists(self.out))
        self.finish(thread, box)

    def test_submission_that_lands_as_the_wait_times_out_counts(self):
        class LateEvent(threading.Event):
            """提出は届いたが、待ちは時間切れと判定された状況を作る。"""

            def wait(self, timeout=None):
                super().wait(timeout)
                return False

        fake = types.SimpleNamespace(Event=LateEvent, Lock=threading.Lock, Thread=threading.Thread)
        stdout = io.StringIO()
        with mock.patch.object(quiz_server, "threading", fake), contextlib.redirect_stdout(stdout):
            thread, box = self.start()
            status, _ = self.request(self.submit_url(box["url"]), self.good_body())
            thread.join(5)
        self.assertEqual(status, 200)
        self.assertEqual(box["code"], 0)
        self.assertIn('"status": "submitted"', stdout.getvalue())
        with open(self.out, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["answers"], {"1": "b", "2": "a"})

    def test_browser_failure_points_to_the_url(self):
        for effect in ({"return_value": False}, {"side_effect": quiz_server.webbrowser.Error("no browser")}):
            with self.subTest(effect=effect):
                stdout = io.StringIO()
                with mock.patch.object(quiz_server.webbrowser, "open", **effect) as opener, \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    code = quiz_server.serve(self.html, self.data, self.out, timeout=0.2, open_browser=True)
                self.assertEqual(code, 2)
                opener.assert_called_once()
                lines = stdout.getvalue().splitlines()
                self.assertTrue(lines[0].startswith("[quiz_server] フォーム: http://127.0.0.1:"))
                self.assertIn("[quiz_server] ブラウザを開けませんでした。上の URL を手動で開いてください", lines)

    def test_browser_success_prints_no_warning(self):
        stdout = io.StringIO()
        with mock.patch.object(quiz_server.webbrowser, "open", return_value=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            quiz_server.serve(self.html, self.data, self.out, timeout=0.2, open_browser=True)
        self.assertNotIn("ブラウザを開けませんでした", stdout.getvalue())


class ClosedIntakeTest(unittest.TestCase):
    """受け付けを閉じたあとの提出。既に保存した提出の重複には 409(フォームは提出済みとして扱う)を返す。"""

    def post_to(self, state):
        server = quiz_server.ThreadingHTTPServer(("127.0.0.1", 0), quiz_server.make_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = "http://127.0.0.1:%d/submit?t=%s" % (server.server_address[1], state["token"])
            body = json.dumps({"session_id": "session-test-01", "answers": {"1": "b", "2": "a"}}).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code
        finally:
            server.shutdown()
            server.server_close()

    def state(self, record):
        return {
            "quiz": QUIZ, "html": "", "out": os.devnull, "token": "tok",
            "record": record, "closed": True, "lock": threading.Lock(), "done": threading.Event(),
        }

    def test_duplicate_after_close_is_409(self):
        self.assertEqual(self.post_to(self.state({"answers": {"1": "b", "2": "a"}})), 409)

    def test_first_submission_after_close_is_503(self):
        self.assertEqual(self.post_to(self.state(None)), 503)


class CodeCommandTest(unittest.TestCase):
    def test_code_command_writes_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "report.quiz.json")
            out = os.path.join(tmp, "report.answers.json")
            with open(data, "w", encoding="utf-8") as f:
                json.dump(QUIZ, f, ensure_ascii=False)
            code = quiz_server.main(["code", "--data", data, "--out", out, "--code", "１：ｂ ２：ａ"])
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as f:
                record = json.load(f)
            self.assertEqual(record["answers"], {"1": "b", "2": "a"})
            self.assertEqual(record["via"], "code")

    def test_code_can_come_from_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "report.quiz.json")
            out = os.path.join(tmp, "report.answers.json")
            with open(data, "w", encoding="utf-8") as f:
                json.dump(QUIZ, f, ensure_ascii=False)
            with mock.patch.object(sys, "stdin", io.StringIO("1:b 2:a\n")), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = quiz_server.main(["code", "--data", data, "--out", out, "--code", "-"])
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["answers"], {"1": "b", "2": "a"})

    def test_code_command_rejects_incomplete_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = os.path.join(tmp, "report.quiz.json")
            out = os.path.join(tmp, "report.answers.json")
            with open(data, "w", encoding="utf-8") as f:
                json.dump(QUIZ, f, ensure_ascii=False)
            self.assertEqual(quiz_server.main(["code", "--data", data, "--out", out, "--code", "1:b"]), 1)
            self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()

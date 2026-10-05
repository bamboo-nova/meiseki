#!/usr/bin/env python3
"""出題フォームを 127.0.0.1 で配信し、提出された回答を answers.json に書いて終了する。

使い方:
    python3 quiz_server.py serve --quiz report.quiz.html --data report.quiz.json --out report.answers.json
    python3 quiz_server.py code --data report.quiz.json --out report.answers.json --code '1:b 2:a'
    python3 quiz_server.py code --data report.quiz.json --out report.answers.json --code - < code.txt

serve は提出を 1 回受け取ると終了する。code は貼り付けられた回答コードから同じ形式のファイルを作る
(--code - なら標準入力から読む)。
標準ライブラリだけで動く。終了コード: 0=回答を保存した / 1=入力の誤り / 2=時間切れ
"""
import argparse
import datetime
import json
import os
import re
import secrets
import sys
import threading
import unicodedata
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from build_quiz import validate_quiz

MAX_BODY = 1_000_000


class AnswerError(ValueError):
    """回答が出題データと対応しないときに送出する。"""


def parse_answer_code(text):
    """「1:b 2:a」形式の回答コードを辞書にする。全角文字と区切りのゆれを吸収する。"""
    normalized = unicodedata.normalize("NFKC", text).lower()
    pairs = re.findall(r"(\d+)\s*[:=]\s*([a-z0-9]+)", normalized)
    if not pairs:
        raise AnswerError("回答コードを読み取れません。「1:b 2:a」の形式で入力してください")
    answers = {}
    for no, choice in pairs:
        key = str(int(no))
        if key in answers:
            raise AnswerError(f"問{key} の回答が 2 つあります")
        answers[key] = choice
    return answers


def validate_answers(quiz, answers):
    """回答が出題データの全問に対応しているかを確かめ、キーを文字列にそろえて返す。"""
    if not isinstance(answers, dict):
        raise AnswerError("answers はオブジェクトにしてください")
    rest = {str(k): v for k, v in answers.items()}
    result = {}
    for q in quiz["questions"]:
        no = str(q["no"])
        if no not in rest:
            raise AnswerError(f"問{no} の回答がありません")
        choice = rest.pop(no)
        if choice not in [c["id"] for c in q["choices"]]:
            raise AnswerError(f"問{no} の回答 {choice!r} は選択肢にありません")
        result[no] = choice
    if rest:
        raise AnswerError("出題していない問題番号があります: " + ", ".join(sorted(rest)))
    return result


def write_answers(out_path, quiz, answers, via):
    """回答ファイルを書く。途中で切れても壊れたファイルが残らないよう、書き終えてから置き換える。"""
    record = {
        "format": 1,
        "session_id": quiz["session_id"],
        "submitted_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "via": via,
        "answers": answers,
    }
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, out_path)
    return record


def load_quiz(data_path):
    with open(data_path, encoding="utf-8") as f:
        return validate_quiz(json.load(f))


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status, body, content_type):
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _json(self, status, obj):
            self._send(status, json.dumps(obj, ensure_ascii=False), "application/json")

        def _authorized(self):
            # ループバック以外の名前で届いた要求は、別のサイトからの呼び出しとみなして断る
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            if host not in ("127.0.0.1", "localhost"):
                return False
            token = parse_qs(urlparse(self.path).query).get("t", [""])[0]
            return secrets.compare_digest(token.encode("utf-8"), state["token"].encode("utf-8"))

        def do_GET(self):
            if urlparse(self.path).path != "/":
                return self._json(404, {"ok": False, "error": "not found"})
            if not self._authorized():
                return self._json(403, {"ok": False, "error": "forbidden"})
            return self._send(200, state["html"], "text/html")

        def do_POST(self):
            if urlparse(self.path).path != "/submit":
                return self._json(404, {"ok": False, "error": "not found"})
            if not self._authorized():
                return self._json(403, {"ok": False, "error": "forbidden"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_BODY:
                    raise AnswerError("本文の大きさが不正です")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(body, dict) or body.get("session_id") != state["quiz"]["session_id"]:
                    raise AnswerError("このフォームは現在のセッションのものではありません")
                answers = validate_answers(state["quiz"], body.get("answers"))
            except ValueError as e:
                return self._json(400, {"ok": False, "error": str(e)})
            with state["lock"]:
                # 保存済みの提出の重複には、受け付けを閉じたあとでも 409 を返す(フォームは提出済みとして扱う)
                if state["record"] is not None:
                    return self._json(409, {"ok": False, "error": "すでに提出済みです"})
                if state["closed"]:
                    return self._json(503, {"ok": False, "error": "受け付けを終了しました"})
                try:
                    state["record"] = write_answers(state["out"], state["quiz"], answers, "server")
                except OSError as e:
                    sys.stderr.write(f"[quiz_server] 回答を保存できませんでした: {e}\n")
                    return self._json(500, {"ok": False, "error": "回答を保存できませんでした"})
            self._json(200, {"ok": True})
            state["done"].set()
            return None

    return Handler


def serve(quiz_html, data_path, out_path, timeout=3600, open_browser=True, port=0, on_ready=None):
    """フォームを配信して提出を待つ。回答を保存したら 0、時間切れなら 2 を返す。"""
    quiz = load_quiz(data_path)
    with open(quiz_html, encoding="utf-8") as f:
        html = f.read()
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if not (os.path.isdir(out_dir) and os.access(out_dir, os.W_OK)):
        raise OSError(f"回答の保存先フォルダに書き込めません: {out_dir}")
    state = {
        "quiz": quiz,
        "html": html,
        "out": out_path,
        "token": secrets.token_urlsafe(16),
        "record": None,
        "closed": False,
        "lock": threading.Lock(),
        "done": threading.Event(),
    }
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    url = f"http://127.0.0.1:{server.server_address[1]}/?t={state['token']}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[quiz_server] フォーム: {url}", flush=True)
    if on_ready:
        on_ready(url)
    if open_browser:
        try:
            opened = webbrowser.open(url)
        except Exception:  # ブラウザが開けなくても、URL を手で開いてもらえば続けられる
            opened = False
        if not opened:
            print("[quiz_server] ブラウザを開けませんでした。上の URL を手動で開いてください", flush=True)
    state["done"].wait(timeout)
    server.shutdown()
    server.server_close()
    # 待ちが切れた直後に提出が届くこともあるため、結果は保存した記録の有無で決める。
    # 判定と同時に受け付けを閉じ、判定のあとで回答ファイルが書かれないようにする
    with state["lock"]:
        state["closed"] = True
        record = state["record"]
    if record is None:
        sys.stderr.write("[quiz_server] 時間内に提出がありませんでした\n")
        return 2
    print(
        json.dumps(
            {"status": "submitted", "out": out_path, "answers": record["answers"]},
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


def save_code(data_path, out_path, code):
    """貼り付けられた回答コードから回答ファイルを作る。"""
    quiz = load_quiz(data_path)
    answers = validate_answers(quiz, parse_answer_code(code))
    record = write_answers(out_path, quiz, answers, "code")
    print(
        json.dumps({"status": "submitted", "out": out_path, "answers": record["answers"]}, ensure_ascii=False),
        flush=True,
    )
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="rikai の回答を受け取る")
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", help="フォームを配信して提出を待つ")
    s.add_argument("--quiz", required=True, help="出題フォーム(quiz.html)")
    s.add_argument("--data", required=True, help="出題データ(quiz.json)")
    s.add_argument("--out", required=True, help="回答の保存先(answers.json)")
    s.add_argument("--timeout", type=float, default=3600, help="提出を待つ秒数(既定 3600)")
    s.add_argument("--no-open", action="store_true", help="ブラウザを自動で開かない")
    s.add_argument("--port", type=int, default=0, help="待ち受けるポート(既定は空きポート)")
    c = sub.add_parser("code", help="回答コードから回答ファイルを作る")
    c.add_argument("--data", required=True, help="出題データ(quiz.json)")
    c.add_argument("--out", required=True, help="回答の保存先(answers.json)")
    c.add_argument("--code", required=True, help="回答コード(例: 1:b 2:a)。- を指定すると標準入力から読む")
    args = ap.parse_args(argv)
    try:
        if args.command == "serve":
            return serve(args.quiz, args.data, args.out, args.timeout, not args.no_open, args.port)
        code = sys.stdin.read() if args.code == "-" else args.code
        return save_code(args.data, args.out, code)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[quiz_server] {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

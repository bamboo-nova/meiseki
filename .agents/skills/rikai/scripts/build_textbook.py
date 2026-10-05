#!/usr/bin/env python3
"""テキストブックの原稿(explainer.tex)を xelatex で PDF にする。

使い方:
    python3 build_textbook.py --input report.explainer.tex --output report.explainer.pdf
    python3 build_textbook.py --escape 'report_v2 & notes.md'
    python3 build_textbook.py --escape - < title.txt      (- なら標準入力から読む)

中間ファイルは一時ディレクトリに作り、出力先には PDF だけを置く。失敗したときは、前の PDF に手を付けない。
フォントにない文字があっても PDF はでき、その文字を標準エラーに警告として出す(終了コードは 0)。
標準ライブラリだけで動く。終了コード: 0=成功 / 1=コンパイル失敗または入力の誤り / 3=xelatex がない
"""
import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
ERROR_LINE = re.compile(r"^(?:\./)?(\S+?\.(?:tex|sty)):(\d+): (.+)$")
NOISE = ("Emergency stop.", " ==> Fatal error occurred")
MISSING_CHAR = re.compile(r"^Missing character: There is no (.+?) \(U\+[0-9A-Fa-f]+\) in font")
TIMEOUT = 300
MAX_RUNS = 5
ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
INSTALL_HINTS = {
    "Darwin": [
        "macOS: brew install --cask mactex-no-gui (Homebrew。数 GB あります)",
        "Homebrew を使わない場合: https://www.tug.org/mactex/ から MacTeX を入れてください",
    ],
    "Linux": [
        "Debian / Ubuntu: sudo apt install texlive-xetex texlive-lang-japanese texlive-latex-extra texlive-pictures",
        "その他のディストリビューション: https://www.tug.org/texlive/ から TeX Live を入れてください",
    ],
    "Windows": [
        "Windows: https://www.tug.org/texlive/windows.html の install-tl-windows.exe で TeX Live を入れてください",
    ],
}


def install_hint(system=None):
    """xelatex の導入方法を、OS に合わせて返す。"""
    lines = INSTALL_HINTS.get(system or platform.system())
    if lines is None:
        lines = ["https://www.tug.org/texlive/ から TeX Live を入れてください"]
    return lines + ["導入したら、ターミナルを開き直してからもう一度ビルドしてください"]


def log(msg):
    print(f"[build_textbook] {msg}", flush=True)


def tex_escape(text):
    """LaTeX の特殊文字を、文字どおり表示される書き方に置き換える。"""
    return "".join(ESCAPES.get(ch, ch) for ch in text)


def summarize_log(text, limit=5):
    """xelatex のログから、エラーの位置と内容を最大 limit 件取り出す。"""
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        m = ERROR_LINE.match(line)
        if m:
            name, number, message = m.group(1), m.group(2), m.group(3)
            where = f"{number} 行目" if name == "main.tex" else f"{os.path.basename(name)} {number} 行目"
            entry = f"{where}: {message}"
            for follow in lines[i + 1:i + 6]:
                if follow.startswith("l." + number):
                    entry += f" ／ {follow.strip()}"
                    break
        elif line.startswith("! ") and not any(noise in line for noise in NOISE):
            entry = line[2:].strip()
        else:
            continue
        if entry not in found:
            found.append(entry)
        if len(found) >= limit:
            break
    if any("cannot be found" in entry and "font" in entry.lower() for entry in found):
        found.append("日本語フォントが見つかりません。IPAexGothic などの日本語フォントを導入してから、もう一度ビルドしてください")
    return found


def missing_characters(log_text):
    """ログの「Missing character」行から、フォントになかった文字を初出順に重複なく返す。"""
    found = []
    for line in log_text.splitlines():
        m = MISSING_CHAR.match(line)
        if m and m.group(1) not in found:
            found.append(m.group(1))
    return found


def _references(work):
    """目次と相互参照のファイルの中身を返す。前回と同じなら、もうコンパイルし直す必要がない。"""
    parts = []
    for name in ("main.toc", "main.aux"):
        path = os.path.join(work, name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                parts.append(f.read())
        else:
            parts.append(b"")
    return parts


def build(input_path, output_path, runs=MAX_RUNS, assets_dir=ASSETS):
    """原稿をビルドする。

    目次と相互参照が前回と変わらなくなるまでコンパイルを繰り返す(最少 2 回、最多 runs 回)。
    目次が 2 ページ以上になると、2 回では目次のページ番号がずれたまま残るためである。
    """
    if shutil.which("xelatex") is None:
        sys.stderr.write(
            "[build_textbook] xelatex が見つかりません。原稿はそのまま残します。"
            "PDF を作るには TeX を導入してください(導入しなくても、出題と絵解きノートは使えます)\n"
        )
        for line in install_hint():
            sys.stderr.write(f"  - {line}\n")
        return 3
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)
    with tempfile.TemporaryDirectory(prefix="rikai-textbook-") as work:
        shutil.copyfile(input_path, os.path.join(work, "main.tex"))
        env = dict(os.environ)
        parts = [os.path.abspath(assets_dir), os.path.dirname(input_path)]
        if env.get("TEXINPUTS"):
            parts.append(env["TEXINPUTS"])
        parts.append("")  # 末尾を空にすると、TeX の既定の検索先が後ろに続く
        env["TEXINPUTS"] = os.pathsep.join(parts)
        cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "main.tex"]
        log_path = os.path.join(work, "main.log")
        previous = None
        for attempt in range(runs):
            try:
                r = subprocess.run(
                    cmd, cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                    text=True, errors="replace", timeout=TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                sys.stderr.write(f"[build_textbook] コンパイルが {TIMEOUT} 秒で終わりませんでした\n")
                return 1
            if r.returncode != 0:
                if os.path.exists(log_path):
                    with open(log_path, encoding="utf-8", errors="replace") as f:
                        text = f.read()
                else:
                    text = r.stdout
                sys.stderr.write("[build_textbook] コンパイルに失敗しました\n")
                entries = summarize_log(text) or ["ログからエラーの位置を特定できませんでした。原稿の構文を確かめてください"]
                for entry in entries:
                    sys.stderr.write(f"  - {entry}\n")
                return 1
            current = _references(work)
            if attempt >= 1 and current == previous:
                break
            previous = current
        missing = []
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8", errors="replace") as f:
                missing = missing_characters(f.read())
        shutil.copyfile(os.path.join(work, "main.pdf"), output_path)
    log(f"完成: {output_path}({os.path.getsize(output_path):,} bytes)")
    if missing:
        sys.stderr.write(
            "[build_textbook] 警告: 次の文字はフォントになく、PDF に出ていません: " + " ".join(missing) + "\n"
        )
        sys.stderr.write("  原稿でほかの書き方に置き換えて、もう一度ビルドしてください\n")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="テキストブックの原稿を PDF にする")
    ap.add_argument("--input", help="原稿(explainer.tex)")
    ap.add_argument("--output", help="出力する PDF")
    ap.add_argument("--runs", type=int, default=MAX_RUNS,
                    help=f"コンパイルの最大回数(既定 {MAX_RUNS}。目次と相互参照が落ち着いたら、そこで止める)")
    ap.add_argument("--escape", help="文字列の特殊文字をエスケープして出力する。- なら標準入力から読む")
    args = ap.parse_args(argv)
    if args.escape is not None:
        text = args.escape
        if text == "-":
            text = sys.stdin.read()
            if text.endswith("\n"):
                text = text[:-1]
        print(tex_escape(text))
        return 0
    if not args.input or not args.output:
        sys.stderr.write("[build_textbook] --input と --output を指定してください\n")
        return 1
    if not os.path.isfile(args.input):
        sys.stderr.write(f"[build_textbook] 原稿が見つかりません: {args.input}\n")
        return 1
    return build(args.input, args.output, args.runs)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_pdf.py — 日本語Markdown → 配色付きのオフラインPDF（pandoc + xelatex）。

Chrome / HTML 経路は使わない（外部通信ゼロ）。IPAexGothic を埋め込み、`style.tex`
で見出し色・コールアウト引用・縞テーブル・ヘッダ/フッタを付ける。ASCIIフェンスを
SVG図（ベクターPDF）へ差し替える機能つき。

必要ツール: pandoc / xelatex(TeX Live) / rsvg-convert(librsvg) / IPAexGothic フォント。
プレビューに ghostscript(gs)。

使用例:
    python3 build_pdf.py --input doc.md --output doc.pdf \\
        --assets assets --figures figures.json \\
        --title "月次レポート" --running-title "月次レポート自動化メモ" \\
        --toc --preview

figures.json（任意）: ASCIIフェンス内に含まれる「署名文字列」を該当SVGへ対応づける。
[
  {"sig": "処理パイプライン（サンプル）", "svg": "pipeline.svg", "caption": "図：…"},
  ...
]
一致したフェンスは ![caption](assets/<svg>.pdf){width=..} に置換し、対象SVGを
rsvg-convert でベクターPDF化して埋め込む。未指定なら ASCII はそのまま等幅表示。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STYLE = os.path.normpath(os.path.join(HERE, "..", "assets", "style.tex"))

# IPAexGothic に無い記号 → フォント収録済みの等価字（ビルド時のみ、原稿は不変）
DEFAULT_GLYPHS = {"✕": "×", "✗": "×", "≈": "≒"}  # ✕✗→× ≈→≒


def log(msg):
    print(f"[build_pdf] {msg}", file=sys.stderr)


def die(msg, code=1):
    log("ERROR: " + msg)
    sys.exit(code)


def check_tools(preview):
    need = ["pandoc", "xelatex", "rsvg-convert"]
    if preview:
        need.append("gs")
    missing = [t for t in need if _which(t) is None]
    if missing:
        die("必要なツールが見つかりません: " + ", ".join(missing) +
            "（例: brew install pandoc librsvg ghostscript / TeX Live）")


def _which(name):
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def svg_to_pdf(assets_dir, svg_name):
    src = os.path.join(assets_dir, svg_name)
    if not os.path.isfile(src):
        die(f"SVGが見つかりません: {src}")
    dst = os.path.splitext(src)[0] + ".pdf"
    subprocess.run(["rsvg-convert", "-f", "pdf", src, "-o", dst], check=True)
    return os.path.basename(dst)


def replace_figures(text, figures, assets_dir, width):
    """ASCIIフェンスを署名一致でSVG画像に差し替える。戻り値: (text, 使用数)."""
    if not figures:
        return text, 0
    used = 0
    parts = re.split(r'(```.*?\n.*?```)', text, flags=re.DOTALL)
    out = []
    for seg in parts:
        rep = None
        if seg.startswith("```"):
            for fig in figures:
                if fig["sig"] in seg:
                    pdf = svg_to_pdf(assets_dir, fig["svg"])
                    cap = fig.get("caption", "")
                    # 絶対パスにして、出力先が assets とどこにあっても xelatex から解決できるようにする
                    abspdf = os.path.abspath(os.path.join(assets_dir, pdf))
                    rep = f'\n![{cap}]({abspdf}){{width={width}}}\n'
                    used += 1
                    break
        out.append(rep if rep is not None else seg)
    return "".join(out), used


def apply_glyphs(text, subs):
    for a, b in subs.items():
        text = text.replace(a, b)
    return text


def tex_escape(s):
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}")]:
        s = s.replace(a, b)
    return s


def main():
    ap = argparse.ArgumentParser(description="日本語Markdown → 配色付きオフラインPDF")
    ap.add_argument("--input", required=True, help="入力Markdown")
    ap.add_argument("--output", required=True, help="出力PDF")
    ap.add_argument("--assets", default=None, help="SVG図のディレクトリ")
    ap.add_argument("--figures", default=None, help="署名→SVG対応のJSON")
    ap.add_argument("--title", default=None, help="表紙タイトル")
    ap.add_argument("--running-title", default="", help="各ページ左上の走りタイトル")
    ap.add_argument("--doc-tag", default="", help="走りタイトル前の小ラベル")
    ap.add_argument("--style", default=DEFAULT_STYLE, help="配色ヘッダ(style.tex)")
    ap.add_argument("--font", default="IPAexGothic", help="本文フォント名")
    ap.add_argument("--fontsize", default="10pt")
    ap.add_argument("--margin", default="16mm")
    ap.add_argument("--img-width", default="88%", help="図の既定幅")
    ap.add_argument("--toc", action="store_true", help="目次を付ける")
    ap.add_argument("--preview", action="store_true", help="1ページ目をPNGプレビュー出力")
    ap.add_argument("--glyph-subs", default="", help="追加字形置換 a=b,c=d")
    args = ap.parse_args()

    check_tools(args.preview)
    if not os.path.isfile(args.input):
        die(f"入力が見つかりません: {args.input}")
    if not os.path.isfile(args.style):
        die(f"style.tex が見つかりません: {args.style}")

    text = open(args.input, encoding="utf-8").read()

    figures = None
    if args.figures:
        figures = json.load(open(args.figures, encoding="utf-8"))
        if not args.assets:
            die("--figures を使うには --assets も必要です")

    text, nfig = replace_figures(text, figures, args.assets, args.img_width)
    if figures is not None:
        miss = [f["svg"] for f in figures if f["sig"] not in "".join(
            re.findall(r'```.*?\n.*?```', open(args.input, encoding='utf-8').read(), flags=re.DOTALL))]
        log(f"図の差し替え: {nfig}/{len(figures)} 件" + (f"（未一致: {miss}）" if miss else ""))

    subs = dict(DEFAULT_GLYPHS)
    for pair in filter(None, args.glyph_subs.split(",")):
        a, _, b = pair.partition("=")
        if a:
            subs[a] = b
    text = apply_glyphs(text, subs)

    work = tempfile.mkdtemp(prefix="jp_pdf_")
    build_md = os.path.join(os.path.dirname(os.path.abspath(args.output)) or ".", "_jp_pdf_build.md")
    open(build_md, "w", encoding="utf-8").write(text)

    # 走りタイトル/タグを style.tex に渡す小ヘッダ
    headvars = os.path.join(work, "_headvars.tex")
    with open(headvars, "w", encoding="utf-8") as f:
        f.write("\\newcommand{\\RunningTitle}{%s}\n" % tex_escape(args.running_title))
        f.write("\\newcommand{\\DocTag}{%s}\n" % tex_escape(args.doc_tag))

    cmd = [
        "pandoc", build_md,
        "-f", "markdown+autolink_bare_uris-implicit_figures",
        "--pdf-engine=xelatex",
        "-H", headvars, "-H", args.style,
        "-V", "documentclass=article",
        "-V", "geometry:a4paper", "-V", f"geometry:margin={args.margin}",
        "-V", f"mainfont={args.font}",
        "-V", "mainfontoptions=AutoFakeBold=2.5,AutoFakeSlant=0.2",
        "-V", f"CJKmainfont={args.font}",
        "-V", "CJKoptions=AutoFakeBold=2.5",
        "-V", "monofont=Menlo",
        "-V", f"fontsize={args.fontsize}",
        "-V", "colorlinks=true", "-V", "linkcolor=teal", "-V", "urlcolor=teal",
        "-o", args.output,
    ]
    if args.title:
        cmd += ["-V", f"title={args.title}"]
    if args.toc:
        cmd += ["--toc", "--toc-depth=2"]

    log("pandoc + xelatex（完全オフライン）でビルド中 …")
    r = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(args.output)) or ".",
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        die("PDF生成に失敗しました（上の xelatex ログを参照）")
    try:
        os.remove(build_md)
    except OSError:
        pass

    size = os.path.getsize(args.output)
    log(f"完成: {args.output}（{size:,} bytes）")

    miss_glyph = r.stderr.count("Missing character")
    if miss_glyph:
        log(f"注意: フォント未収録グリフの警告が {miss_glyph} 件（--glyph-subs で置換を検討）")

    if args.preview:
        png = os.path.splitext(args.output)[0] + "_p1.png"
        subprocess.run(["gs", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=png16m",
                        "-r120", "-dFirstPage=1", "-dLastPage=1",
                        f"-sOutputFile={png}", args.output],
                       check=True, capture_output=True)
        log(f"プレビュー: {png}")


if __name__ == "__main__":
    main()

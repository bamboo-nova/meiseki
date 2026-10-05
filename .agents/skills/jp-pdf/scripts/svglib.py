# -*- coding: utf-8 -*-
"""svglib — 日本語ドキュメント向けの一貫した SVG 図を作るための最小プリミティブ。

設計方針:
- 角丸ボックス・矢印・ラベル・チップと限定パレットで、読みやすい図を素早く作る。
- テキストが枠を超える場合は **フォントサイズを実際に縮めて** 収める（`fitfs`）。
  SVG の `textLength`（引き伸ばし指定）は rsvg-convert の PDF/Cairo バックエンドで
  無視されるため使わない。フォント縮小なら PNG でも PDF でも同じく収まる。

使い方（作図スクリプト側）:
    from svglib import *          # header/footer/box/arrow/label/title/chip/save/PAL ...
    s  = header(860, 300)
    s += title(30, 34, "見出し")
    s += box(40, 60, 220, 60, ["1行目", "2行目"], "anchor")
    s += footer()
    save("assets", "figure.svg", s)
"""
import os
import html

# 日本語はまず IPAexGothic（PDF 本文と統一）。モノスペースはコード片用。
FONT = "'IPAexGothic','IPAexゴシック','Noto Sans CJK JP',sans-serif"
MONO = "'IPAexGothic','SFMono-Regular','Menlo',monospace"

# パレット: 論理名 -> (塗り, 枠, 文字)
PAL = {
    "human":   ("#e0e7ff", "#4338ca", "#312e81"),
    "anchor":  ("#ccfbf1", "#0f766e", "#134e4a"),
    "cap":     ("#fef3c7", "#b45309", "#78350f"),
    "neutral": ("#f1f5f9", "#475569", "#1e293b"),
    "danger":  ("#fee2e2", "#b91c1c", "#7f1d1d"),
    "ok":      ("#dcfce7", "#15803d", "#14532d"),
    "dark":    ("#1e293b", "#0f172a", "#e2e8f0"),
}


def esc(s):
    return html.escape(str(s), quote=True)


def estw(s, fs):
    """描画幅の概算: 全角(非ASCII)=fs, ASCII=0.56*fs。"""
    w = 0.0
    for ch in s:
        w += fs if ord(ch) > 0x7f else fs * 0.56
    return w


def fitfs(s, fs, avail):
    """文字列が幅 `avail` を超える場合に、収まるよう縮小したフォントサイズを返す。
    全バックエンドで有効（textLength と違い実寸のグリフを縮める）。"""
    if avail:
        w = estw(s, fs)
        if w > avail:
            return max(fs * avail / w * 0.985, fs * 0.5)
    return fs


def fss(v):
    """font-size をコンパクトに整形。"""
    return f"{v:.2f}".rstrip("0").rstrip(".")


def header(w, h):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'font-family="{FONT}" width="{w}" height="{h}">\n'
        f'<defs>'
        f'<marker id="ar"  markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L8,3 L0,6 Z" fill="#475569"/></marker>'
        f'<marker id="arR" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L8,3 L0,6 Z" fill="#b91c1c"/></marker>'
        f'<marker id="arG" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L8,3 L0,6 Z" fill="#15803d"/></marker>'
        f'</defs>\n'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="#ffffff"/>\n'
    )


def footer():
    return "</svg>\n"


def box(x, y, w, h, lines, pal="neutral", fs=14, rx=10, bold_first=False, align="middle"):
    """角丸ボックス＋複数行テキスト。各行は枠内に収まるよう自動でフォント縮小。"""
    fill, stroke, tc = PAL[pal]
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
         f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>\n')
    if isinstance(lines, str):
        lines = [lines]
    lh = fs + 6
    total = lh * len(lines)
    ty = y + h / 2 - total / 2 + fs
    ax = {"middle": x + w / 2, "start": x + 14}
    anchor = {"middle": "middle", "start": "start"}[align]
    avail = w - 24
    for i, ln in enumerate(lines):
        weight = "700" if (bold_first and i == 0) else "400"
        lfs = fitfs(ln, fs, avail)
        s += (f'<text x="{ax[align]}" y="{ty + i * lh}" fill="{tc}" font-size="{fss(lfs)}" '
              f'font-weight="{weight}" text-anchor="{anchor}">{esc(ln)}</text>\n')
    return s


def label(x, y, s, fs=13, color="#334155", anchor="middle", weight="400", mono=False, maxw=None):
    """自由配置のテキスト。maxw 指定時ははみ出さないよう縮小。"""
    ff = f' font-family="{MONO}"' if mono else ""
    lfs = fitfs(s, fs, maxw)
    return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{fss(lfs)}" font-weight="{weight}" '
            f'text-anchor="{anchor}"{ff}>{esc(s)}</text>\n')


def arrow(x1, y1, x2, y2, color="#475569", marker="ar", width=2.0, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="{width}"{d} marker-end="url(#{marker})"/>\n')


def title(x, y, s, fs=16, color="#0f172a"):
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{fs}" font-weight="700">{esc(s)}</text>\n'


def chip(cx, cy, s, pal, fs=13):
    """中央 cx を基準にした角丸タグ。幅はテキスト実測から算出（はみ出さない）。"""
    fill, stroke, tc = PAL[pal]
    w = 24 + estw(s, fs)
    x = cx - w / 2
    return (f'<rect x="{x}" y="{cy-15}" width="{w}" height="30" rx="15" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.4"/>'
            f'<text x="{cx}" y="{cy+5}" fill="{tc}" font-size="{fs}" text-anchor="middle" '
            f'font-weight="600">{esc(s)}</text>\n')


def save(out_dir, name, svg):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return path

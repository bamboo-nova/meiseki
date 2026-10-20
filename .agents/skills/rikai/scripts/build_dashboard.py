#!/usr/bin/env python3
"""study.md の集まりから、学習進捗のダッシュボード(dashboard.html)を組み立てる。

使い方:
    python3 build_dashboard.py --rikai-dir docs/.rikai            # docs/.rikai/dashboard.html を作る
    python3 build_dashboard.py --rikai-dir docs                   # docs/.rikai を探して同じことをする
    python3 build_dashboard.py --root . --lang en                 # 配下の .rikai/ をすべてまとめ、./.rikai/dashboard.html を作る

読むのは各 study.md の frontmatter だけで、本文は読まない。出力は読むだけの静的 HTML で、
同じ study.md の集まりからは常に同じ HTML になる(生成時刻は埋め込まない)。
YAML は study-format.md が定めるブロック形式の部分集合を自前で読む(標準ライブラリに読み手がないため)。
読めない study.md があっても止めず、その資料のカードに理由を出して他の資料は載せる。
終了コード: 0=全件読めた / 1=入力の誤り / 2=読めない study.md があった
"""
import argparse
import datetime
import html
import json
import os
import re
import sys

TEMPLATE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "dashboard-template.html"
)
STATUSES = ("復習中", "卒業", "要再抽出")
SCHEMA_VERSIONS = (1, 2, 3)
MISREAD_LIMIT = 5
SKIP_DIRS = {"node_modules", ".git"}
DEFAULT_LANG = "ja"

# 固定の文言。ja と en は同じキーを持つ。ほかの言語は en で表示する
UI = {
    "ja": {
        "title": "学習進捗ダッシュボード",
        "eyebrow": "{folder} ／ 最新の挑戦 {latest}",
        "never": "まだありません",
        "lead": "この .rikai フォルダにある資料の学習状態を、study.md から集計したものです。解説は各資料の絵解きノートとテキストブックにあります。",
        "documents": "資料",
        "topics": "論点",
        "復習中": "復習中",
        "卒業": "卒業",
        "要再抽出": "要再抽出",
        "docs_heading": "資料ごとの進捗",
        "attempted": "挑戦済み {a} / {t} 論点",
        "latest": "最新の挑戦",
        "next_review": "次回の復習対象",
        "none_next": "復習待ちの論点はありません。",
        "misread": "誤読の多い段落",
        "none_misread": "誤答はまだありません。",
        "wrong_times": "誤答 {n} 回",
        "link_html": "絵解きノート",
        "link_pdf": "テキストブック",
        "link_tex": "テキストブックの原稿",
        "link_study": "study.md（生データ）",
        "record": "論点ごとの記録",
        "record_hint": "（{n} 論点。開くと挑戦履歴）",
        "tally": "正解 {c}・誤答 {w}",
        "untried": "未挑戦",
        "correct": "正解",
        "wrong": "誤答",
        "manual_at": "手動で卒業: {at}",
        "reextract_note": "原文に根拠の段落が見つからないため、出題対象外です。",
        "manual_heading": "手動で卒業にした論点",
        "manual_lead": "出題に正答したのではなく、「復習済みにして」の指示で卒業にした論点です。",
        "none_manual": "ありません。",
        "manual": "手動",
        "no_reason": "理由の記載なし",
        "unreadable": "この study.md は読み取れませんでした",
        "footer": "状態の正本は各 study.md の frontmatter です。この画面は読むだけで、何も書き換えません。論点を手動で卒業にしたいときは、rikai スキルに「この論点は復習済みにして」と頼んでください。",
    },
    "en": {
        "title": "Learning progress dashboard",
        "eyebrow": "{folder} / latest attempt {latest}",
        "never": "none yet",
        "lead": "Progress of every document in this .rikai folder, aggregated from study.md. Explanations live in each document's picture notebook and textbook.",
        "documents": "documents",
        "topics": "topics",
        "復習中": "Reviewing",
        "卒業": "Mastered",
        "要再抽出": "Needs re-extraction",
        "docs_heading": "Progress by document",
        "attempted": "{a} / {t} topics attempted",
        "latest": "Latest attempt",
        "next_review": "Next review",
        "none_next": "No topics are waiting for review.",
        "misread": "Most misread passages",
        "none_misread": "No wrong answers yet.",
        "wrong_times": "{n} wrong",
        "link_html": "Picture notebook",
        "link_pdf": "Textbook",
        "link_tex": "Textbook manuscript",
        "link_study": "study.md (raw)",
        "record": "Record by topic",
        "record_hint": "({n} topics; expand for attempt history)",
        "tally": "{c} correct / {w} wrong",
        "untried": "not attempted",
        "correct": "correct",
        "wrong": "wrong",
        "manual_at": "Mastered by hand: {at}",
        "reextract_note": "Not asked: the supporting passage could not be found in the source.",
        "manual_heading": "Topics mastered by hand",
        "manual_lead": "Topics marked as mastered on request (\"mark this as reviewed\") rather than by answering a quiz.",
        "none_manual": "None.",
        "manual": "manual",
        "no_reason": "no reason given",
        "unreadable": "This study.md could not be read",
        "footer": "The source of truth is each study.md's frontmatter. This page only reads; it never writes. To mark a topic as mastered by hand, ask the rikai skill to \"mark this topic as reviewed\".",
    },
}


class StudyFormatError(ValueError):
    """study.md の frontmatter が読めない、または形式に合わないときに送出する。"""


# ---------------------------------------------------------------------------
# YAML の部分集合の読み手
# ---------------------------------------------------------------------------
_INT = re.compile(r"^-?(0|[1-9][0-9]*)$")
_FRONT = re.compile(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", re.S)


def _scalar(text, no):
    t = text.strip()
    if t == "" or t in ("null", "~"):
        return None
    if t == "true":
        return True
    if t == "false":
        return False
    if t == "[]":
        return []
    if t == "{}":
        return {}
    if t[0] == '"':
        if len(t) < 2 or not t.endswith('"'):
            raise StudyFormatError(f"{no} 行目: 二重引用符が閉じていません")
        try:
            return json.loads(t)
        except ValueError:
            raise StudyFormatError(f"{no} 行目: 二重引用符の中のエスケープを読めません") from None
    if t[0] == "'":
        if len(t) < 2 or not t.endswith("'"):
            raise StudyFormatError(f"{no} 行目: 単一引用符が閉じていません")
        return t[1:-1].replace("''", "'")
    if _INT.match(t):
        return int(t)
    if t[0] in "&*|>[{!%@`":
        raise StudyFormatError(f"{no} 行目: 対象外の YAML 記法です({t[0]!r} で始まる値)")
    return t


def _is_seq_line(content):
    return content == "-" or content.startswith("- ")


def _split_key(content, no):
    if content.endswith(":") and ": " not in content:
        key, rest = content[:-1], ""
    elif ": " in content:
        key, rest = content.split(": ", 1)
    else:
        raise StudyFormatError(f"{no} 行目: 「キー: 値」の形になっていません(複数行の値は読めません)")
    key = _scalar(key, no)
    if not isinstance(key, str) or not key:
        raise StudyFormatError(f"{no} 行目: キーが文字列ではありません")
    return key, rest.strip()


def _parse_block(lines, i, indent):
    if _is_seq_line(lines[i][1]):
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_seq(lines, i, indent):
    items = []
    while i < len(lines):
        ind, content, no = lines[i]
        if ind < indent or not _is_seq_line(content):
            break
        if ind > indent:
            raise StudyFormatError(f"{no} 行目: 予期しないインデントです")
        rest = "" if content == "-" else content[1:].lstrip()
        if rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1, lines[i + 1][0])
            else:
                value, i = None, i + 1
        elif _looks_like_map(rest):
            # 「- key: value」は、キーの桁をインデントとするマッピングの先頭行として読み直す
            lines[i] = (ind + len(content) - len(rest), rest, no)
            value, i = _parse_map(lines, i, lines[i][0])
        else:
            value, i = _scalar(rest, no), i + 1
        items.append(value)
    return items, i


def _looks_like_map(content):
    if content[0] in "\"'":
        return False
    return content.endswith(":") or ": " in content


def _parse_map(lines, i, indent):
    obj = {}
    while i < len(lines):
        ind, content, no = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise StudyFormatError(f"{no} 行目: 予期しないインデントです(複数行の値は読めません)")
        if _is_seq_line(content):
            raise StudyFormatError(f"{no} 行目: マッピングの中に配列の項目があります")
        key, rest = _split_key(content, no)
        if key in obj:
            raise StudyFormatError(f"{no} 行目: キー {key!r} が重複しています")
        if rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1, lines[i + 1][0])
            elif i + 1 < len(lines) and lines[i + 1][0] == indent and _is_seq_line(lines[i + 1][1]):
                value, i = _parse_seq(lines, i + 1, indent)
            else:
                value, i = None, i + 1
        else:
            value, i = _scalar(rest, no), i + 1
        obj[key] = value
    return obj, i


def parse_yaml_subset(text):
    """ブロック形式のマッピング・配列・スカラーだけを読む。それ以外の記法は StudyFormatError。"""
    lines = []
    for no, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.lstrip(" ")
        if stripped.startswith("\t"):
            raise StudyFormatError(f"{no} 行目: タブでインデントされています")
        lines.append((len(raw) - len(stripped), stripped.rstrip(), no))
    if not lines:
        return {}
    value, i = _parse_block(lines, 0, lines[0][0])
    if i != len(lines):
        raise StudyFormatError(f"{lines[i][2]} 行目: 予期しないインデントです")
    return value


def read_frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = _FRONT.match(text)
    if not m:
        raise StudyFormatError("先頭の --- で囲まれた frontmatter がありません")
    data = parse_yaml_subset(m.group(1))
    if not isinstance(data, dict):
        raise StudyFormatError("frontmatter がマッピングではありません")
    return data


# ---------------------------------------------------------------------------
# 形式の確認
# ---------------------------------------------------------------------------
def _require(cond, message):
    if not cond:
        raise StudyFormatError(message)


def validate_study(data):
    """frontmatter の形を確かめ、そのまま返す。足りないものは StudyFormatError で示す。"""
    _require(isinstance(data, dict), "frontmatter がマッピングではありません")
    _require(data.get("schema_version") in SCHEMA_VERSIONS, "schema_version が 1〜3 ではありません")
    topics = data.get("topics")
    _require(isinstance(topics, list), "topics が配列ではありません")
    seen = set()
    for t in topics:
        _require(isinstance(t, dict), "topics の項目がマッピングではありません")
        tid = t.get("id")
        _require(isinstance(tid, str) and tid, "論点に id がありません")
        _require(tid not in seen, f"論点 id {tid} が重複しています")
        seen.add(tid)
        _require(t.get("status") in STATUSES, f"{tid}: status が 3 種のいずれでもありません")
        anchor = t.get("anchor")
        _require(isinstance(anchor, dict), f"{tid}: anchor がありません")
        hp = anchor.get("heading_path")
        _require(isinstance(hp, list) and all(isinstance(h, str) for h in hp), f"{tid}: heading_path が文字列の配列ではありません")
        _require(isinstance(anchor.get("quote"), str), f"{tid}: quote が文字列ではありません")
        title = t.get("title")
        _require(title is None or isinstance(title, str), f"{tid}: title が文字列ではありません")
        attempts = t.get("attempts")
        _require(isinstance(attempts, list), f"{tid}: attempts が配列ではありません")
        for a in attempts:
            _require(isinstance(a, dict), f"{tid}: attempts の項目がマッピングではありません")
            _require(isinstance(a.get("attempted_at"), str), f"{tid}: attempted_at が文字列ではありません")
            _require(isinstance(a.get("correct"), bool), f"{tid}: correct が真偽値ではありません")
        manual = t.get("manual_graduation")
        if manual is not None:
            _require(isinstance(manual, dict) and isinstance(manual.get("at"), str), f"{tid}: manual_graduation に at がありません")
            reason = manual.get("reason")
            _require(reason is None or isinstance(reason, str), f"{tid}: manual_graduation.reason が文字列でも null でもありません")
    return data


# ---------------------------------------------------------------------------
# 集計
# ---------------------------------------------------------------------------
_MIN_DT = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def parse_dt(text):
    """タイムゾーンつき ISO 8601 を aware な datetime にする。読めなければ None。"""
    if not isinstance(text, str):
        return None
    t = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        d = datetime.datetime.fromisoformat(t)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d


def _dt_key(text):
    return parse_dt(text) or _MIN_DT


def _title(topic):
    title = topic.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    # schema 1 には title がない。id は読者に見せないので、引用の冒頭で代える
    quote = topic["anchor"]["quote"].strip()
    return quote if len(quote) <= 40 else quote[:40] + "…"


def misread_paragraphs(topics, limit=MISREAD_LIMIT):
    """還流レポートと同じ規則で誤答を段落ごとに集計する(study-format.md §5)。"""
    groups = {}
    for t in topics:
        key = (tuple(t["anchor"]["heading_path"]), t["anchor"]["quote"])
        for a in t["attempts"]:
            if a["correct"]:
                continue
            g = groups.setdefault(key, {"count": 0, "last": None, "titles": {}, "min_id": t["id"]})
            g["count"] += 1
            if g["last"] is None or _dt_key(a["attempted_at"]) > _dt_key(g["last"]):
                g["last"] = a["attempted_at"]
            g["titles"][t["id"]] = _title(t)
            g["min_id"] = min(g["min_id"], t["id"])
    rows = []
    for (heading_path, quote), g in groups.items():
        rows.append({
            "heading_path": list(heading_path),
            "quote": quote,
            "count": g["count"],
            "last": g["last"],
            "titles": [g["titles"][k] for k in sorted(g["titles"])],
            "_min_id": g["min_id"],
        })
    rows.sort(key=lambda r: (-r["count"], -_dt_key(r["last"]).timestamp(), r["_min_id"]))
    for r in rows:
        del r["_min_id"]
    return rows[:limit]


def next_review(topics):
    """誤答を経験した復習中の論点。前回の挑戦が誤答だったものを先に、あとは id 順。"""
    rows = []
    for t in topics:
        if t["status"] != "復習中" or not any(not a["correct"] for a in t["attempts"]):
            continue
        last = max(t["attempts"], key=lambda a: _dt_key(a["attempted_at"]))
        rows.append((0 if not last["correct"] else 1, t["id"], _title(t)))
    rows.sort()
    return [title for _, _, title in rows]


def summarize_topics(topics):
    counts = {s: 0 for s in STATUSES}
    latest = None
    attempted = 0
    manual = []
    for t in topics:
        counts[t["status"]] += 1
        if t["attempts"]:
            attempted += 1
        for a in t["attempts"]:
            if latest is None or _dt_key(a["attempted_at"]) > _dt_key(latest):
                latest = a["attempted_at"]
        m = t.get("manual_graduation")
        if m is not None:
            manual.append({"title": _title(t), "at": m["at"], "reason": m.get("reason")})
    manual.sort(key=lambda r: (-_dt_key(r["at"]).timestamp(), r["title"]))
    return {
        "total": len(topics),
        "counts": counts,
        "attempted": attempted,
        "latest": latest,
        "next_review": next_review(topics),
        "misread": misread_paragraphs(topics),
        "manual": manual,
        "records": [topic_record(t) for t in sorted(topics, key=lambda t: t["id"])],
    }


def topic_record(topic):
    """論点 1 つの、人が読む記録(題名・状態・挑戦履歴)。id は含めない。"""
    attempts = sorted(topic["attempts"], key=lambda a: _dt_key(a["attempted_at"]))
    manual = topic.get("manual_graduation")
    return {
        "title": _title(topic),
        "status": topic["status"],
        "manual": None if manual is None else {"at": manual["at"], "reason": manual.get("reason")},
        "correct": sum(1 for a in attempts if a["correct"]),
        "wrong": sum(1 for a in attempts if not a["correct"]),
        "attempts": [
            {
                "at": a["attempted_at"],
                "correct": a["correct"],
                "aspect": a.get("aspect") if isinstance(a.get("aspect"), str) else "",
                "question": a.get("question") if isinstance(a.get("question"), str) else "",
            }
            for a in attempts
        ],
    }


def source_name(study_path):
    base = os.path.basename(study_path)
    return base[: -len(".study.md")] if base.endswith(".study.md") else base


def _rel(target, out_path):
    return os.path.relpath(target, os.path.dirname(os.path.abspath(out_path))).replace(os.sep, "/")


def collect_document(study_path, out_path, label):
    """study.md 1 つを読んで集計する。読めなければ error に理由を入れて返す。"""
    name = source_name(study_path)
    folder = os.path.dirname(os.path.abspath(study_path))
    links = {"study": _rel(study_path, out_path)}
    for key, suffix in (("html", ".explainer.html"), ("pdf", ".explainer.pdf"), ("tex", ".explainer.tex")):
        candidate = os.path.join(folder, name + suffix)
        links[key] = _rel(candidate, out_path) if os.path.isfile(candidate) else None
    doc = {"name": label, "links": links, "error": None, "summary": None}
    try:
        data = validate_study(read_frontmatter(study_path))
    except (OSError, UnicodeDecodeError) as e:
        doc["error"] = str(e)
        return doc
    except StudyFormatError as e:
        doc["error"] = str(e)
        return doc
    doc["summary"] = summarize_topics(data["topics"])
    return doc


def find_study_files(rikai_dir):
    return sorted(
        os.path.join(rikai_dir, f) for f in os.listdir(rikai_dir) if f.endswith(".study.md")
    )


def find_rikai_dirs(root):
    found = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if os.path.basename(dirpath) == ".rikai":
            found.append(dirpath)
            dirnames[:] = []
    return found


def aggregate(docs):
    counts = {s: 0 for s in STATUSES}
    total = 0
    latest = None
    manual = []
    for d in docs:
        s = d["summary"]
        if s is None:
            continue
        total += s["total"]
        for k in STATUSES:
            counts[k] += s["counts"][k]
        if s["latest"] and (latest is None or _dt_key(s["latest"]) > _dt_key(latest)):
            latest = s["latest"]
        for m in s["manual"]:
            manual.append(dict(m, document=d["name"]))
    manual.sort(key=lambda r: (-_dt_key(r["at"]).timestamp(), r["document"], r["title"]))
    return {"documents": len(docs), "total": total, "counts": counts, "latest": latest, "manual": manual}


# ---------------------------------------------------------------------------
# 描画
# ---------------------------------------------------------------------------
def _e(text):
    return html.escape(str(text), quote=True)


def fmt_dt(text, ui):
    d = parse_dt(text)
    if d is None:
        return ui["never"] if not text else _e(text)
    return d.strftime("%Y-%m-%d %H:%M")


def _percent(n, total):
    return 0.0 if total == 0 else round(100.0 * n / total, 1)


def render_bar(counts, total):
    segs = []
    for cls, key in (("ok", "卒業"), ("ng", "復習中"), ("re", "要再抽出")):
        w = _percent(counts[key], total)
        if w > 0:
            segs.append(f'<span class="{cls}" style="width:{w}%"></span>')
    return '<div class="bar" aria-hidden="true">' + "".join(segs) + "</div>"


def render_counts(counts, ui, total):
    items = []
    for cls, key in (("ok", "卒業"), ("ng", "復習中"), ("re", "要再抽出")):
        items.append(f'<li><span class="dot {cls}"></span>{_e(ui[key])} <b>{counts[key]}</b></li>')
    return f'<ul class="counts">{"".join(items)}<li class="total">{_e(ui["topics"])} <b>{total}</b></li></ul>'


def render_summary(overall, ui):
    return (
        '<section class="summary">'
        f'<div class="stat"><b>{overall["documents"]}</b><span>{_e(ui["documents"])}</span></div>'
        f'<div class="stat"><b>{overall["total"]}</b><span>{_e(ui["topics"])}</span></div>'
        f'<div class="stat ok"><b>{overall["counts"]["卒業"]}</b><span>{_e(ui["卒業"])}</span></div>'
        f'<div class="stat ng"><b>{overall["counts"]["復習中"]}</b><span>{_e(ui["復習中"])}</span></div>'
        f'<div class="stat re"><b>{overall["counts"]["要再抽出"]}</b><span>{_e(ui["要再抽出"])}</span></div>'
        "</section>"
    )


def render_links(links, ui):
    out = []
    for key, label in (("html", "link_html"), ("pdf", "link_pdf"), ("tex", "link_tex"), ("study", "link_study")):
        if key == "tex" and links.get("pdf"):
            continue  # PDF があれば原稿へのリンクは出さない
        if links.get(key):
            out.append(f'<a href="{_e(links[key])}">{_e(ui[label])}</a>')
    return '<p class="links">' + " ".join(out) + "</p>"


def render_document(doc, ui):
    parts = [f'<article class="doc"><h3>{_e(doc["name"])}</h3>']
    if doc["error"]:
        parts.append(f'<p class="error">{_e(ui["unreadable"])}: {_e(doc["error"])}</p>')
        parts.append(render_links(doc["links"], ui))
        parts.append("</article>")
        return "".join(parts)
    s = doc["summary"]
    parts.append(render_bar(s["counts"], s["total"]))
    parts.append(render_counts(s["counts"], ui, s["total"]))
    parts.append(
        f'<p class="meta">{_e(ui["attempted"].format(a=s["attempted"], t=s["total"]))} ／ '
        f'{_e(ui["latest"])}: {fmt_dt(s["latest"], ui)}</p>'
    )
    parts.append(f'<h4>{_e(ui["next_review"])}</h4>')
    if s["next_review"]:
        parts.append("<ol>" + "".join(f"<li>{_e(t)}</li>" for t in s["next_review"]) + "</ol>")
    else:
        parts.append(f'<p class="muted">{_e(ui["none_next"])}</p>')
    parts.append(f'<h4>{_e(ui["misread"])}</h4>')
    if s["misread"]:
        rows = []
        for r in s["misread"]:
            path = " › ".join(r["heading_path"]) if r["heading_path"] else ""
            rows.append(
                '<li>'
                f'<span class="chip ng">{_e(ui["wrong_times"].format(n=r["count"]))}</span> '
                f'<span class="titles">{_e("、".join(r["titles"]))}</span>'
                f'<span class="path">{_e(path)}</span>'
                f'<blockquote>{_e(r["quote"])}</blockquote>'
                "</li>"
            )
        parts.append('<ol class="misread">' + "".join(rows) + "</ol>")
    else:
        parts.append(f'<p class="muted">{_e(ui["none_misread"])}</p>')
    parts.append(render_records(s["records"], ui))
    parts.append(render_links(doc["links"], ui))
    parts.append("</article>")
    return "".join(parts)


def render_status_chip(record, ui):
    status = record["status"]
    cls = {"卒業": "ok", "復習中": "ng", "要再抽出": "re"}[status]
    label = ui[status] + (f"（{ui['manual']}）" if record["manual"] else "")
    return f'<span class="chip {cls}">{_e(label)}</span>'


def render_records(records, ui):
    """論点ごとの記録を折りたたみで出す。開くと挑戦履歴が時系列で読める。"""
    if not records:
        return ""
    items = []
    for r in records:
        tally = ui["tally"].format(c=r["correct"], w=r["wrong"]) if r["attempts"] else ui["untried"]
        body = []
        if r["manual"]:
            reason = r["manual"]["reason"] or ui["no_reason"]
            body.append(f'<p class="meta">{_e(ui["manual_at"].format(at=fmt_dt(r["manual"]["at"], ui)))} ／ {_e(reason)}</p>')
        if r["status"] == "要再抽出":
            body.append(f'<p class="meta">{_e(ui["reextract_note"])}</p>')
        if r["attempts"]:
            rows = []
            for a in r["attempts"]:
                mark = ui["correct"] if a["correct"] else ui["wrong"]
                cls = "ok" if a["correct"] else "ng"
                aspect = f'<span class="path">{_e(a["aspect"])}</span>' if a["aspect"] else ""
                rows.append(
                    "<li>"
                    f'<span class="when">{fmt_dt(a["at"], ui)}</span> <span class="chip {cls}">{_e(mark)}</span> '
                    f"{aspect}<span class=\"question\">{_e(a['question'])}</span>"
                    "</li>"
                )
            body.append('<ol class="attempts">' + "".join(rows) + "</ol>")
        items.append(
            "<li><details>"
            f'<summary>{render_status_chip(r, ui)} <b>{_e(r["title"])}</b> <span class="tally">{_e(tally)}</span></summary>'
            f'<div class="rbody">{"".join(body)}</div>'
            "</details></li>"
        )
    hint = ui["record_hint"].format(n=len(records))
    return (
        '<details class="record"><summary>'
        f'<b>{_e(ui["record"])}</b><span class="hint">{_e(hint)}</span></summary>'
        '<ul class="topics">' + "".join(items) + "</ul></details>"
    )


def render_manual(manual, ui):
    if not manual:
        return f'<p class="muted">{_e(ui["none_manual"])}</p>'
    rows = []
    for m in manual:
        reason = m["reason"] if m["reason"] else ui["no_reason"]
        rows.append(
            "<li>"
            f'<span class="chip ok">{_e(ui["卒業"])}（{_e(ui["manual"])}）</span> '
            f'<b>{_e(m["title"])}</b><span class="path">{_e(m["document"])} ／ {fmt_dt(m["at"], ui)}</span>'
            f'<span class="reason">{_e(reason)}</span>'
            "</li>"
        )
    return '<ul class="manual">' + "".join(rows) + "</ul>"


def render(docs, folder_label, lang, template_path=TEMPLATE):
    ui = UI.get(lang, UI["en"])
    overall = aggregate(docs)
    with open(template_path, encoding="utf-8") as f:
        page = f.read()
    values = {
        "{{LANG}}": _e(lang),
        "{{TITLE}}": _e(ui["title"]),
        "{{EYEBROW}}": _e(ui["eyebrow"].format(folder=folder_label, latest="")).rstrip() + " " + fmt_dt(overall["latest"], ui),
        "{{LEAD}}": _e(ui["lead"]),
        "{{SUMMARY}}": render_summary(overall, ui),
        "{{DOCS_HEADING}}": _e(ui["docs_heading"]),
        "{{DOCS}}": "".join(render_document(d, ui) for d in docs),
        "{{MANUAL_HEADING}}": _e(ui["manual_heading"]),
        "{{MANUAL_LEAD}}": _e(ui["manual_lead"]),
        "{{MANUAL}}": render_manual(overall["manual"], ui),
        "{{FOOTER}}": _e(ui["footer"]),
    }
    for key, value in values.items():
        if page.count(key) == 0:
            raise ValueError(f"雛形に {key} がありません")
        page = page.replace(key, value)
    if "{{" in page:
        raise ValueError("雛形に埋められていない差し込み口が残っています")
    return page


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def resolve_rikai_dir(path):
    path = os.path.abspath(path)
    if os.path.basename(path) == ".rikai" and os.path.isdir(path):
        return path
    nested = os.path.join(path, ".rikai")
    if os.path.isdir(nested):
        return nested
    raise ValueError(f".rikai フォルダが見つかりません: {path}")


def build(rikai_dir=None, root=None, out=None, lang=DEFAULT_LANG):
    """ダッシュボードを書き、(出力パス, 資料の一覧) を返す。"""
    if (rikai_dir is None) == (root is None):
        raise ValueError("--rikai-dir と --root のどちらか一方を指定してください")
    if rikai_dir is not None:
        rikai_dir = resolve_rikai_dir(rikai_dir)
        out = os.path.abspath(out or os.path.join(rikai_dir, "dashboard.html"))
        base = os.path.dirname(rikai_dir)
        studies = [(p, source_name(p)) for p in find_study_files(rikai_dir)]
        folder_label = os.path.basename(base) or base
    else:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            raise ValueError(f"フォルダがありません: {root}")
        out = os.path.abspath(out or os.path.join(root, ".rikai", "dashboard.html"))
        studies = []
        for d in find_rikai_dirs(root):
            parent = os.path.relpath(os.path.dirname(d), root).replace(os.sep, "/")
            prefix = "" if parent == "." else parent + "/"
            studies.extend((p, prefix + source_name(p)) for p in find_study_files(d))
        studies.sort(key=lambda s: s[1])
        folder_label = os.path.basename(root) or root
    os.makedirs(os.path.dirname(out), exist_ok=True)
    docs = [collect_document(p, out, label) for p, label in studies]
    page = render(docs, folder_label, lang)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page)
    os.replace(tmp, out)
    return out, docs


def main(argv=None):
    ap = argparse.ArgumentParser(description="rikai の学習進捗ダッシュボードを組み立てる")
    ap.add_argument("--rikai-dir", help=".rikai フォルダ(またはそれを含むフォルダ)。このフォルダの資料だけをまとめる")
    ap.add_argument("--root", help="起点のフォルダ。配下の .rikai フォルダをすべてまとめる")
    ap.add_argument("--out", help="出力先(既定: 対象の .rikai/dashboard.html)")
    ap.add_argument("--lang", default=DEFAULT_LANG, help="固定の文言の言語(ja または en。既定 ja。ほかの言語は en)")
    args = ap.parse_args(argv)
    try:
        out, docs = build(args.rikai_dir, args.root, args.out, args.lang)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[build_dashboard] {e}\n")
        return 1
    unreadable = [d["name"] for d in docs if d["error"]]
    for name in unreadable:
        sys.stderr.write(f"[build_dashboard] 読み取れない study.md: {name}\n")
    print(
        json.dumps(
            {"status": "built", "out": out, "documents": len(docs), "unreadable": unreadable},
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 2 if unreadable else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塾内テストの結果を取り込む（単元確認テスト・組分けテストなど）。

何のためか
----------
宿題の評価だけでは、その単元が「分かっている」かどうかは半分しか見えない。
ノートはよく書けていても、テストでは落とす子がいる。塾内テストの点を
単元に割り当てて重ねると、理解度（insight.py）がずっと確かになる。

表の形は校舎や学年でちがい、まだ決まっていない。そこで3つとも読む。

    大問（単元）ごとの点   席番号, 比例(20), 一次関数(30), …
    合計点だけ            席番号, 合計, 偏差値
    設問ごとの正誤         席番号, 1-(1), 1-(2), 2-(1), …   （○×・1/0）

**名前は受け取らない。** 1列目は席番号（中2R-01）。名前らしい見出しの列が
あれば、表ごと取り込まない。取り込んだ文字は残さず、sid と点数だけを残す。

置き場所
--------
    <ROOT>/schools/<校舎>/scores.json
    {"tests": {"<ID>": {
        "key": "<コースの鍵>", "name": "単元確認テスト", "date": "2026-09-05",
        "kind": "units" | "total" | "questions",
        "cols": [{"label": "比例", "max": 20, "lessons": [3, 4]}],
        "rows": {"<sid>": [18, 12, null]},
        "by": "<講師のsid>", "at": 秒}}}
"""

import csv
import datetime as _dt
import math
import re
import secrets
import threading
import time
import unicodedata

import paths

MAX_ROWS = 300
MAX_COLS = 80
MAX_TESTS = 400          # 1校舎あたり。古いものから講師が消す

# 名前や連絡先らしい見出し。1つでもあれば取り込まない。
NAME_WORDS = ("氏名", "名前", "なまえ", "ふりがな", "フリガナ", "name", "保護者", "電話",
              "tel", "mail", "メール", "住所", "塾生番号", "生徒番号", "学籍")
# 点数ではない列（読み飛ばす）。
SKIP_WORDS = ("偏差値", "順位", "平均", "得点率", "判定", "クラス", "コース", "学年",
              "性別", "欠席", "備考", "rank")
TOTAL_WORDS = ("合計", "総合", "総点", "得点", "点数", "total", "score")
MARK_OK = {"○", "◯", "〇", "o", "O", "✓", "✔", "1", "正", "t", "T"}
MARK_NG = {"×", "✕", "✗", "x", "X", "0", "誤", "f", "F", "-", "－"}

HEAD_MAX = re.compile(
    r"^(.*?)\s*(?:[（(]\s*(?:満点)?\s*(\d+(?:\.\d+)?)\s*点?\s*[)）]"
    r"|[/／]\s*(\d+(?:\.\d+)?)\s*点?"
    r"|\s(\d+(?:\.\d+)?)\s*点)$")
# 設問の見出し：「1」「(1)」「問1」「Q3」「1-(2)」「大問2-3」「2-1」
QHEAD = re.compile(r"^(?:大問|問|Q|q|第)?\s*[（(]?(\d+)[)）]?"
                   r"(?:\s*[-‐－–ー.・]\s*[（(]?(\d+)[)）]?)?\s*(?:問)?$")

_LOCK = paths.GUARD          # 置き場にひとつだけの鍵（スレッドにもプロセスにも効く。paths.Guard）


def _n(s):
    return unicodedata.normalize("NFKC", str(s if s is not None else "")).strip()


# ------------------------------------------------------------------
# 保管
# ------------------------------------------------------------------
def _file(school):
    return paths.school_file(school, "scores.json")


def load(school):
    d = paths.load(_file(school), {}) or {}
    if not isinstance(d.get("tests"), dict):
        d["tests"] = {}
    return d


def save(school, d):
    paths.save(_file(school), d)


def tests_of(school, key, data=None):
    """そのコースのテスト。日付の新しい順。"""
    d = data if data is not None else load(school)
    out = []
    for tid, t in (d.get("tests") or {}).items():
        if t.get("key") == key:
            x = dict(t)
            x["id"] = tid
            out.append(x)
    out.sort(key=lambda x: (x.get("date") or "", x.get("at") or 0), reverse=True)
    return out


def remove(school, tid):
    with _LOCK:
        d = load(school)
        if tid not in d["tests"]:
            return None
        t = d["tests"].pop(tid)
        save(school, d)
    return t


def drop_student(school, sid):
    """退塾した生徒の点を消す。"""
    with _LOCK:
        d = load(school)
        changed = False
        for t in d["tests"].values():
            if sid in (t.get("rows") or {}):
                t["rows"].pop(sid, None)
                changed = True
        if changed:
            save(school, d)
    return changed


# ------------------------------------------------------------------
# 表を読む
# ------------------------------------------------------------------
def split_rows(text):
    """CSV か、Excel から貼り付けたタブ区切り。空の行は捨てる。"""
    t = str(text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    lines = [ln for ln in t.split("\n") if ln.strip()]
    if not lines:
        return []
    delim = "\t" if lines[0].count("\t") > lines[0].count(",") else ","
    return [[c.strip() for c in r] for r in csv.reader(lines, delimiter=delim)]


def _num(s):
    s = _n(s).replace("点", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _mark(s):
    s = _n(s)
    if s == "":
        return None
    if s in MARK_OK:
        return 1
    if s in MARK_NG:
        return 0
    return "?"


def _head_max(h):
    """「比例(20)」「比例/20」「比例 20点」→（比例, 20）。満点が無ければ（見出し, None）。"""
    h = _n(h)
    m = HEAD_MAX.match(h)
    if m and m.group(1).strip():
        mx = m.group(2) or m.group(3) or m.group(4)
        return m.group(1).strip(), float(mx)
    return h, None


def _has(words, h):
    low = _n(h).lower()
    return any(w.lower() in low for w in words)


def parse(text):
    """表を読んで、形・列・行を返す。**保存はしない**（確かめる画面に出す）。

    返す形
        {"kind", "cols": [{"label", "max", "idx": [列番号…], "q": 設問数}],
         "rows": [{"seat": 席の文字, "vals": [列ごとの点 or None]}],
         "errors": [...], "warnings": [...]}
    """
    rows = split_rows(text)
    res = {"kind": None, "cols": [], "rows": [], "errors": [], "warnings": []}
    if len(rows) < 2:
        res["errors"].append("見出しの行と、生徒の行が要ります")
        return res
    head = rows[0]
    if len(head) > MAX_COLS + 1:
        res["errors"].append("列が多すぎます（%d列まで）" % MAX_COLS)
        return res
    bad = [h for h in head if _has(NAME_WORDS, h)]
    if bad:
        res["errors"].append("名前や連絡先の列（%s）があります。席番号と点数だけの表にしてください"
                             % "・".join(_n(b) for b in bad[:3]))
        return res

    body = rows[1:]
    maxrow = None
    if body and ("満点" in _n(body[0][0]) or "配点" in _n(body[0][0])):
        maxrow, body = body[0], body[1:]
    body = [r for r in body if r and _n(r[0]) and not _has(("平均", "合計", "満点"), r[0])]
    if len(body) > MAX_ROWS:
        res["errors"].append("生徒の行が多すぎます（%d行まで）" % MAX_ROWS)
        return res
    if not body:
        res["errors"].append("生徒の行がありません")
        return res

    # 点数の列を選ぶ。1列目は席番号。
    idx = [i for i in range(1, len(head)) if _n(head[i]) and not _has(SKIP_WORDS, head[i])]

    def col_vals(i):
        return [(r[i] if i < len(r) else "") for r in body]

    # 設問ごとの正誤：○× か 1/0 だけが並ぶ列が4本以上
    marks = [i for i in idx if not _has(TOTAL_WORDS, head[i])
             and all(_mark(v) in (0, 1, None) for v in col_vals(i))
             and any(_n(v) for v in col_vals(i))
             and any(_n(v) not in ("0", "1", "") for v in col_vals(i)) or
             (QHEAD.match(_n(head[i])) and all(_mark(v) in (0, 1, None) for v in col_vals(i))
              and any(_n(v) for v in col_vals(i)))]
    marks = [i for i in marks if not _has(TOTAL_WORDS, head[i])]
    if len(marks) >= 4 and len(marks) >= len([i for i in idx if not _has(TOTAL_WORDS, head[i])]) * 0.8:
        groups, order = {}, []
        for i in marks:
            h = _n(head[i])
            m = QHEAD.match(h)
            if m and m.group(2):
                g = ("大問%s" % m.group(1)) if not h.startswith("大問") else "大問%s" % m.group(1)
            elif m:
                g = "全体"
            else:
                g = re.sub(r"[\s\-‐－–ー.・]*[（(]?\d+[)）]?$", "", h).strip() or "全体"
            if g not in groups:
                groups[g] = []
                order.append(g)
            groups[g].append(i)
        res["kind"] = "questions"
        for g in order:
            res["cols"].append({"label": g, "max": float(len(groups[g])), "idx": groups[g],
                                "q": len(groups[g])})
        for r in body:
            vals = []
            for c in res["cols"]:
                got = [_mark(r[i] if i < len(r) else "") for i in c["idx"]]
                seen = [x for x in got if x in (0, 1)]
                vals.append(float(sum(seen)) if seen else None)
            res["rows"].append({"seat": _n(r[0]), "vals": vals})
        return res

    numeric = [i for i in idx if any(_num(v) is not None for v in col_vals(i))]
    units = [i for i in numeric if not _has(TOTAL_WORDS, head[i])]
    totals = [i for i in numeric if _has(TOTAL_WORDS, head[i])]
    if units:
        res["kind"] = "units"
        pick = units
        if totals:
            res["warnings"].append("合計の列は読み飛ばしました（大問ごとの点を使います）")
    elif totals or len(numeric) == 1:
        res["kind"] = "total"
        pick = (totals or numeric)[:1]
    else:
        res["errors"].append("点数の列が見つかりません")
        return res

    for i in pick:
        label, mx = _head_max(head[i])
        if maxrow is not None and i < len(maxrow) and _num(maxrow[i]):
            mx = _num(maxrow[i])
        if res["kind"] == "total":
            label = "合計"
        res["cols"].append({"label": label, "max": mx, "idx": [i], "q": 0})
    for r in body:
        vals = []
        for c in res["cols"]:
            i = c["idx"][0]
            vals.append(_num(r[i]) if i < len(r) else None)
        res["rows"].append({"seat": _n(r[0]), "vals": vals})
    for c in res["cols"]:
        if not c["max"]:
            res["warnings"].append("「%s」の満点が分かりません。確かめる画面で入れてください" % c["label"])
    return res


# ------------------------------------------------------------------
# 席番号で生徒に合わせる
# ------------------------------------------------------------------
def seat_key(s):
    s = _n(s).upper().replace(" ", "")
    return re.sub(r"[‐－–ー―−]", "-", s)


def match_seats(parsed, roster):
    """roster: [{"sid", "label": "中2R-01", "seat": "01"}]。

    「中2R-01」で合わせる。数字だけ（01・1）なら、そのコースで一意のときだけ合わせる。
    返す形 ({席の文字: sid}, [合わなかった席])"""
    by_label = {seat_key(r["label"]): r["sid"] for r in roster if r.get("label")}
    by_num = {}
    for r in roster:
        m = re.search(r"(\d+)$", _n(r.get("seat") or r.get("label") or ""))
        if m:
            by_num.setdefault(int(m.group(1)), []).append(r["sid"])
    got, miss = {}, []
    for row in parsed.get("rows") or []:
        k = seat_key(row["seat"])
        sid = by_label.get(k)
        if not sid and re.match(r"^\d+$", k):
            cand = by_num.get(int(k)) or []
            sid = cand[0] if len(cand) == 1 else None
        if sid:
            got[row["seat"]] = sid
        else:
            miss.append(row["seat"])
    return got, miss


# ------------------------------------------------------------------
# 列を単元（授業の回）に割り当てる
# ------------------------------------------------------------------
def _date(s):
    try:
        return _dt.datetime.strptime(str(s), "%Y-%m-%d").date()
    except ValueError:
        return None


def _bigrams(t):
    t = re.sub(r"[\s　・、。（）()\-]", "", _n(t))
    return {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else ({t} if t else set())


def similar(a, b):
    """単元名どうしが同じものを指していそうか（0〜1）。"""
    na = re.sub(r"[\s　]", "", _n(a))
    nb = re.sub(r"[\s　]", "", _n(b))
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if len(na) >= 2 and len(nb) >= 2 and (na in nb or nb in na):
        return 0.9
    x, y = _bigrams(na), _bigrams(nb)
    return (2.0 * len(x & y) / (len(x) + len(y))) if (x and y) else 0.0


def window_lessons(lessons, date, days=35):
    """テストの日から前 days 日の回（総復習の回は外す）。無ければ直近の5回。"""
    d = _date(date)
    past = [l for l in lessons if l.get("date") and (d is None or _date(l["date"]) and _date(l["date"]) <= d)]
    past.sort(key=lambda l: l.get("date") or "")
    if d is not None:
        lo = d - _dt.timedelta(days=days)
        win = [l for l in past if _date(l["date"]) > lo]
    else:
        win = past[-5:]
    win = win or past[-5:]
    return [l for l in win if "総復習" not in str(l.get("topic") or "")] or win


def auto_map(parsed, lessons, date):
    """列ごとの単元（第何回）。見出しと topic が合えばその回、合わなければ範囲の回すべて。"""
    win = window_lessons(lessons, date)
    past = [l for l in lessons if l.get("date") and (not _date(date) or l["date"] <= date)]
    out = []
    for c in parsed.get("cols") or []:
        best, score = None, 0.0
        if parsed.get("kind") != "total":
            for l in (win + [x for x in past if x not in win]):
                s = similar(c["label"], l.get("topic"))
                if s > score:
                    best, score = l, s
        if best is not None and score >= 0.5:
            out.append([int(best["n"])])
        else:
            out.append([int(l["n"]) for l in win])
    return out


# ------------------------------------------------------------------
# 取り込む
# ------------------------------------------------------------------
def build(key, name, date, parsed, seatmap, mapping, maxes, by, now=None):
    """確かめたあとの中身から、保存する1件を作る。"""
    name = _n(name)[:40]
    if not name:
        raise ValueError("テストの名前を入れてください")
    if not _date(date):
        raise ValueError("実施日を入れてください（年-月-日）")
    if parsed.get("errors"):
        raise ValueError(parsed["errors"][0])
    cols = []
    for i, c in enumerate(parsed.get("cols") or []):
        mx = None
        if maxes and i < len(maxes) and maxes[i] not in (None, ""):
            try:
                mx = float(maxes[i])
            except (TypeError, ValueError):
                mx = None
        mx = mx or c.get("max")
        if not mx or mx <= 0:
            raise ValueError("「%s」の満点を入れてください" % c["label"])
        les = mapping[i] if (mapping and i < len(mapping)) else []
        les = sorted({int(x) for x in (les or []) if str(x).isdigit() and 0 < int(x) < 1000})
        cols.append({"label": _n(c["label"])[:40], "max": mx, "lessons": les})
    rows = {}
    for r in parsed.get("rows") or []:
        sid = seatmap.get(r["seat"])
        if not sid:
            continue
        vals = []
        for i, v in enumerate(r["vals"][:len(cols)]):
            if v is None:
                vals.append(None)
            else:
                vals.append(round(max(0.0, min(float(v), cols[i]["max"])), 2))
        if any(v is not None for v in vals):
            rows[sid] = vals
    if not rows:
        raise ValueError("席番号が合う生徒がいません")
    return {"key": key, "name": name, "date": str(date), "kind": parsed.get("kind"),
            "cols": cols, "rows": rows, "by": by, "at": int(now or time.time())}


def put(school, rec):
    with _LOCK:
        d = load(school)
        if len(d["tests"]) >= MAX_TESTS:
            raise ValueError("テストの記録が多すぎます。古いものを消してください")
        tid = "t" + secrets.token_hex(4)
        d["tests"][tid] = rec
        save(school, d)
    return tid


def unit_pcts(tests, sid):
    """その生徒の、単元（第何回）ごとのテストの出来（%）。同じ単元は新しいテストを優先する。

    返す形 {n: {"pct": 0〜100, "date": 実施日, "name": テスト名}}"""
    out = {}
    for t in sorted(tests, key=lambda x: (x.get("date") or "", x.get("at") or 0)):
        vals = (t.get("rows") or {}).get(sid)
        if not vals:
            continue
        for i, c in enumerate(t.get("cols") or []):
            if i >= len(vals) or vals[i] is None or not c.get("max"):
                continue
            p = int(math.floor(100.0 * vals[i] / c["max"] + 0.5))
            for n in c.get("lessons") or []:
                out[int(n)] = {"pct": p, "date": t.get("date"), "name": t.get("name")}
    return out

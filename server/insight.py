#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""理解度と、講師への提案。

講師が成績のページで知りたいのは2つだけである。

    どのコースにテコ入れが要るか
    どの生徒に、何を足す（置き換える）か

そのために、生徒 × 単元（コースの授業の回）ごとに理解度を組み立てる。

根拠は **あるものだけ** を重ねる
--------------------------------
    宿題の評価     その回の束に付いた評価      5→100 4→80 3→60 2→40 1→20   重み 0.45
    塾内テスト     その回に割り当てた列の点     点÷満点                      重み 0.35
    毎日テスト     単元名が topic と合う問題    できた回数÷答えた回数           重み 0.15
    対策の丸つけ   単元名が合う落とした記録     (出た−落とした)÷出た            重み 0.05

無い根拠は0点ではなく「無い」。重みはある根拠の中で割り直す。
**画面には必ず根拠を添える**（どれがいくつか）。数字だけ出すと、講師は信じない。

**理解度は保存しない。** 評価・テスト・進捗から毎回組み立てる。保存すると、
評価を付け直しても理解度が変わらない画面ができる。

このモジュールは計算だけを持つ。ファイルは読まない（tube_server が集めて渡す）。
検査（server/test_insight.py）が、ファイル無しで全部を走らせる。
"""

import datetime as _dt
import math
import time

import ratescale
import scores as SC
import personal as PR

WEIGHTS = (("hw", 0.45), ("test", 0.35), ("daily", 0.15), ("prep", 0.05))
# 講師の評価が無いまま期限から7日過ぎた紙の宿題（写真は出ている）は、仮に4（80%）とみなす。
# 「講師が付け忘れる＝生徒が最低評価」を防ぐ（本人）。4を基準に、良ければ5、そうでなければ下3段。
# 講師の宿題チェックでは未評価のまま数える（check_rows の v は None のまま。prov で印だけ）。
PROVISIONAL_DAYS = 7
PROVISIONAL_V = 4
YELLOW = 70          # これ未満の単元は黄色（講師の決め）
RECENT = 5           # 直近いくつの単元を見るか（平均・要注意の判定）
SHOW = 8             # 図に並べる単元の数（6週以上が見えるように。2026-09-12 本人）
MIN_DAILY = 3        # 毎日テストは3回以上答えたときだけ根拠にする
DISMISS_DAYS = 21    # 見送った提案を、同じ生徒・単元・種類で出し直さない日数

KIND_WORD = {"redo": "解き直し", "app": "アプリで復習", "lighten": "量を減らす",
             "basic": "上位の宿題を基本に"}


def half_up(x):
    """四捨五入（32.5 → 33）。Python の round は偶数に寄せる（32.5 → 32）ので使わない ――
    画面（Math.round）と1ずれて、同じ生徒の理解度が2か所で違って見える。"""
    return int(math.floor(float(x) + 0.5))


def unit_match(unit, topic):
    return SC.similar(unit, topic) >= 0.6


# ------------------------------------------------------------------
# 束（その回の宿題）と、生徒1人ぶんの状態
# ------------------------------------------------------------------
def lesson_bundles(asgs):
    """コースの宿題を回ごとに。{n: [宿題…]}"""
    by = {}
    for a in asgs or []:
        ls = a.get("lesson") or {}
        try:
            n = int(ls.get("n"))
        except (TypeError, ValueError):
            continue
        by.setdefault(n, []).append(a)
    return by


def due_of(items):
    return max([int(a.get("dueAt") or 0) for a in items] or [0])


def student_bundle(items, sid):
    """その生徒が受け取るもの、紙の束、束の代表（写真を出す先）。

    代表は生徒の画面（app/js/homework.js の head）と**同じ決まり**にする ――
    その生徒の宿題のうち、紙で採点するものを「上位でない→ID の小さい順」に並べた先頭。
    生徒ごとの宿題（personal）があると、代表は生徒によって違う。"""
    mine = [a for a in items if sid in (a.get("students") or [])]
    paper = [a for a in mine
             if (a.get("route") or "app") == "paper" and a.get("graded") is not False]
    paper.sort(key=lambda a: (1 if a.get("extra") else 0, a.get("id") or ""))
    return {"mine": mine, "paper": paper, "head": paper[0] if paper else None,
            "apps": [a for a in mine if (a.get("route") or "app") != "paper"],
            "plain": [a for a in mine
                      if (a.get("route") or "app") == "paper" and a.get("graded") is False]}


def student_state(bundle, sid, ratings_db, subs_db, hw_blob, now_ms=None):
    """その回の、その生徒の状態（写真・評価・アプリの達成・提出）。
    prov … 評価が無いまま期限から PROVISIONAL_DAYS 過ぎ、写真（か先生の取り込み）はある → 仮の4"""
    head = bundle["head"]
    st = {"assigned": bool(bundle["mine"]), "head": head["id"] if head else None,
          "targets": [a["id"] for a in bundle["paper"]], "files": [], "at": None,
          "seen": False, "note": "", "v": None, "ratedAt": None, "appDone": None,
          "returned": [], "returnedAt": None, "origin": "", "pruned": False, "prov": False, "worry": False,
          "personal": any(a.get("personal") for a in bundle["mine"])}
    if head:
        sub = ((subs_db or {}).get(head["id"]) or {}).get(sid) or {}
        st["files"] = [f.get("name") for f in (sub.get("files") or []) if f.get("name")]
        st["at"] = sub.get("at")
        st["seen"] = bool(sub.get("seen"))
        st["note"] = sub.get("note") or ""
        # 講師が返した添削（赤を入れた紙の写真・PDF）。生徒の画面と講師の画面の両方が見る
        ret = sub.get("returned") or {}
        st["returned"] = [f.get("name") for f in (ret.get("files") or []) if f.get("name")]
        st["returnedAt"] = ret.get("at")
        st["origin"] = sub.get("origin") or ("student" if sub.get("files") else "")
        st["pruned"] = bool(sub.get("pruned"))          # 写真は保存期間を過ぎて消した。出した事実は残る
        # 評価は束の全件に同じ値が入る。代表に無ければほかの件も見る。
        for a in bundle["paper"]:
            r = ((ratings_db or {}).get(a["id"]) or {}).get(sid)
            v = ratescale.value(r)
            if v is not None:
                st["v"], st["ratedAt"] = v, (r or {}).get("at")
                st["worry"] = bool((r or {}).get("worry"))     # 理解が心配（講師だけ。生徒には出さない）
                break
    if head and st["v"] is None and (st["files"] or st["pruned"] or st["origin"] == "teacher"):
        due = due_of(bundle["paper"])
        now_ms = now_ms or time.time() * 1000
        if due and now_ms - due >= PROVISIONAL_DAYS * 86400 * 1000:
            st["prov"] = True
    if bundle["apps"]:
        hw = hw_blob or {}
        st["appDone"] = all((hw.get(a["id"]) or {}).get("completedAt") for a in bundle["apps"])
    if head:
        st["submitted"] = bool(st["files"]) or (st["v"] or 0) >= 1
    elif bundle["apps"]:
        st["submitted"] = bool(st["appDone"])
    else:
        st["submitted"] = None           # 出すだけの宿題しかない回は、提出を数えない
    return st


# ------------------------------------------------------------------
# 根拠
# ------------------------------------------------------------------
def daily_by_topic(cards, unit_of, topics):
    """毎日テストの出来を単元ごとに。{n: %}。

    cards は進捗の記録（{項目ID: [iv, ef, due, reps, lapse, seen, known]}）、
    unit_of は {項目ID: 単元名}、topics は {n: topic}。"""
    per = {}
    for cid, c in (cards or {}).items():
        u = (unit_of or {}).get(cid)
        if not u or not isinstance(c, list) or len(c) < 5:
            continue
        reps, lapse = int(c[3] or 0), int(c[4] or 0)
        if reps <= 0:
            continue
        e = per.setdefault(u, [0, 0])
        e[0] += reps
        e[1] += max(0, reps - lapse)
    out = {}
    for n, topic in (topics or {}).items():
        a = ok = 0
        for u, (r, g) in per.items():
            if unit_match(u, topic):
                a += r
                ok += g
        if a >= MIN_DAILY:
            out[n] = half_up(100.0 * ok / a)
    return out


def prep_by_topic(units, topics):
    """対策テストで落とした単元（weak.json の units）を単元ごとに。{n: %}"""
    out = {}
    for n, topic in (topics or {}).items():
        a = w = 0
        for u, e in (units or {}).items():
            if unit_match(u, topic):
                a += int(e.get("n") or 0)
                w += int(e.get("w") or 0)
        if a >= 2:
            out[n] = half_up(100.0 * max(0, a - w) / a)
    return out


def combine(ev):
    tot = wsum = 0.0
    for k, wt in WEIGHTS:
        v = (ev or {}).get(k)
        if v is None:
            continue
        tot += wt * float(v)
        wsum += wt
    return half_up(tot / wsum) if wsum else None


def mean(vals):
    vals = [v for v in vals if v is not None]
    return half_up(sum(vals) / float(len(vals))) if vals else None


def histogram(vals, bins=10):
    """0〜100 を bins 等分した人数。100 は最後の区切りに入れる。"""
    out = [0] * bins
    for v in vals:
        if v is None:
            continue
        i = min(bins - 1, max(0, int(v * bins // 100)))
        out[i] += 1
    return out


# ------------------------------------------------------------------
# コース × 生徒 × 単元
# ------------------------------------------------------------------
def course_matrix(ctx, now_ms=None):
    """コースの単元（期限の来た回）と、生徒ごとの理解度・提出。

    ctx
        plan      lessons.json のそのコース
        asgs      そのコースの宿題（lesson.key が一致するもの）
        ratings   ratings.json
        subs      submissions.json
        tests     scores.tests_of の戻り
        blobs     {sid: 進捗の blob（cards・hw）}
        unit_of   {項目ID: 単元名}（そのコースの教科・学年の問題）
        weak      {sid: {単元名: {"w", "n"}}}（そのコースの教科）
        roster    [{"sid", "label"}]
    """
    now_ms = now_ms or time.time() * 1000
    plan = ctx.get("plan") or {}
    lessons = {}
    for l in plan.get("lessons") or []:
        try:
            lessons[int(l.get("n"))] = l
        except (TypeError, ValueError):
            continue
    by = lesson_bundles(ctx.get("asgs"))
    due_ns = sorted(n for n, items in by.items()
                    if due_of(items) and due_of(items) <= now_ms
                    and any(a.get("graded") is not False or (a.get("route") or "app") != "paper"
                            for a in items))
    topics = {n: (lessons.get(n) or {}).get("topic") or "" for n in due_ns}

    # **その回に、提出を観測する手段があったか。** 紙の束に写真も評価も1件も無い回は、
    # 講師が写真の提出を使っていない回である。そこを全員「未提出」と数えると、
    # 提出率 0% が並び、「提出が続かない」という誤った提案まで出る。
    # 観測していないものを、やっていないと言わない（CLAUDE.md「紙とアプリの併走」）。
    observed = {}
    for n in due_ns:
        obs = False
        for a in by[n]:
            if (a.get("route") or "app") != "paper":
                obs = True                  # アプリの宿題は、いつも観測している
                break
            if a.get("graded") is False:
                continue
            if (ctx.get("ratings") or {}).get(a["id"]) or (ctx.get("subs") or {}).get(a["id"]):
                obs = True
                break
        observed[n] = obs

    roster = list(ctx.get("roster") or [])
    known = {r["sid"] for r in roster}
    for items in by.values():
        for a in items:
            for s in a.get("students") or []:
                if s not in known:
                    known.add(s)
                    roster.append({"sid": s, "label": s})

    students = []
    for r in roster:
        sid = r["sid"]
        blob = (ctx.get("blobs") or {}).get(sid) or {}
        tp = SC.unit_pcts(ctx.get("tests") or [], sid)
        daily = daily_by_topic(blob.get("cards"), ctx.get("unit_of"), topics)
        prep = prep_by_topic((ctx.get("weak") or {}).get(sid), topics)
        cells = {}
        for n in due_ns:
            b = student_bundle(by[n], sid)
            if not b["mine"] and n not in tp:
                continue
            st = student_state(b, sid, ctx.get("ratings"), ctx.get("subs"), blob.get("hw"))
            ev = {"hw": ratescale.PCT.get(st["v"]) if st["v"] else (ratescale.PCT[PROVISIONAL_V] if st.get("prov") else None),
                  "test": (tp.get(n) or {}).get("pct"),
                  "daily": daily.get(n), "prep": prep.get(n)}
            cells[n] = {"u": combine(ev), "ev": ev, "v": st["v"], "prov": bool(st.get("prov")),
                        "sub": st["submitted"] if (st["assigned"] and observed.get(n)) else None,
                        "files": len(st["files"]), "personal": st["personal"],
                        "test": tp.get(n)}
        recent = [n for n in due_ns if n in cells][-RECENT:]
        subs_recent = [cells[n]["sub"] for n in recent if cells[n]["sub"] is not None]
        students.append({
            "sid": sid, "label": r.get("label") or sid,
            "cells": cells,
            "avg": mean([cells[n]["u"] for n in recent]),
            "subRate": (half_up(100.0 * sum(1 for x in subs_recent if x) / len(subs_recent))
                        if subs_recent else None),
            "missed": sum(1 for x in subs_recent if x is False),
        })
    students.sort(key=lambda s: s["label"])

    units = []
    for n in due_ns:
        l = lessons.get(n) or {}
        vals = [s["cells"][n]["u"] for s in students if n in s["cells"]]
        subs = [s["cells"][n]["sub"] for s in students
                if n in s["cells"] and s["cells"][n]["sub"] is not None]
        und = mean(vals)
        units.append({
            "n": n, "topic": l.get("topic") or "", "label": l.get("label"), "review": bool(l.get("review")),
            "date": l.get("date") or "",
            "dueAt": due_of(by[n]),
            "und": und, "undN": len([v for v in vals if v is not None]),
            "low": len([v for v in vals if v is not None and v < YELLOW]),
            "sub": (half_up(100.0 * sum(1 for x in subs if x) / len(subs)) if subs else None),
            "subDone": sum(1 for x in subs if x), "subN": len(subs),
            "yellow": und is not None and und < YELLOW,
        })
    return {"units": units, "students": students}


def overview_row(course, matrix):
    """成績の「すべて」に並べる札1枚ぶん。"""
    # 総復習の回は単元ではない。推移・最新・「つづけて70%未満」の数えに入れない。
    units = [u for u in matrix["units"] if not u.get("review")][-SHOW:]
    rated = [u for u in units if u["und"] is not None]
    latest = rated[-1] if rated else None
    subs = [u for u in units if u["sub"] is not None]
    last_sub = subs[-1] if subs else None
    yellow_run = 0
    for u in reversed(rated):
        if u["yellow"]:
            yellow_run += 1
        else:
            break
    avgs = [s["avg"] for s in matrix["students"] if s["avg"] is not None]
    reasons = []
    if latest and latest["yellow"]:
        reasons.append("%s が %d%%" % (utext(latest), latest["und"]))
    if yellow_run >= 2:
        reasons.append("%d回つづけて70%%未満" % yellow_run)
    if last_sub and last_sub["sub"] is not None and last_sub["sub"] < 70:
        reasons.append("提出 %d%%" % last_sub["sub"])
    return {
        "key": course.get("key"), "name": course.get("name"), "grade": course.get("grade"),
        "subject": course.get("subject"),
        "students": len(matrix["students"]),
        "units": [{"n": u["n"], "topic": u["topic"], "label": u.get("label"), "review": u.get("review", False),
                   "und": u["und"], "sub": u["sub"],
                   "yellow": u["yellow"]} for u in units],
        "latest": latest and {"n": latest["n"], "topic": latest["topic"], "label": latest.get("label"),
                              "und": latest["und"]},
        "sub": last_sub and last_sub["sub"],
        "low50": len([a for a in avgs if a <= 50]),
        "flag": bool(reasons), "reasons": reasons,
    }


def student_trend(matrix, sid, lessons):
    """生徒1人の、単元ごとと月ごとの推移。"""
    s = [x for x in matrix["students"] if x["sid"] == sid]
    if not s:
        return {"units": [], "months": []}
    s = s[0]
    dates = {int(l.get("n")): l.get("date") or "" for l in (lessons or []) if l.get("n") is not None}
    units = []
    for u in matrix["units"]:
        c = s["cells"].get(u["n"])
        if not c:
            continue
        units.append({"n": u["n"], "topic": u["topic"], "label": u.get("label"), "date": u["date"], "u": c["u"],
                      "ev": c["ev"], "v": c["v"], "sub": c["sub"], "classU": u["und"]})
    months = {}
    for x in units:
        d = dates.get(x["n"]) or x["date"]
        if x["u"] is None or not d:
            continue
        months.setdefault(d[:7], []).append(x["u"])
    return {"units": units,
            "months": [{"month": m, "u": mean(v), "n": len(v)} for m, v in sorted(months.items())],
            "avg": s["avg"], "subRate": s["subRate"]}


# ------------------------------------------------------------------
# 宿題チェック（講師の「今日やること」と、チェックのページ）
# ------------------------------------------------------------------
def check_rows(items, roster, ratings_db, subs_db, blobs):
    """その回の全員の行と、数（提出・評価ずみ・評価まだ・未提出）。"""
    sids = []
    for a in items:
        for s in a.get("students") or []:
            if s not in sids:
                sids.append(s)
    labels = {r["sid"]: r.get("label") or r["sid"] for r in roster or []}
    rows = []
    for sid in sids:
        b = student_bundle(items, sid)
        if not b["paper"]:
            continue                        # 紙の束が無い生徒（アプリだけ）は写真を見ない
        st = student_state(b, sid, ratings_db, subs_db, ((blobs or {}).get(sid) or {}).get("hw"))
        rows.append({
            "sid": sid, "label": labels.get(sid, sid),
            "head": st["head"], "targets": st["targets"],
            "files": st["files"], "at": st["at"], "seen": st["seen"], "note": st["note"],
            "v": st["v"], "ratedAt": st["ratedAt"], "personal": st["personal"], "worry": st["worry"],
            "returned": st["returned"], "returnedAt": st["returnedAt"], "origin": st["origin"], "pruned": st["pruned"], "prov": st["prov"],
            "items": [{"title": a.get("title") or "", "route": a.get("route") or "app",
                       "extra": bool(a.get("extra")), "personal": bool(a.get("personal")),
                       "graded": a.get("graded") is not False}
                      for a in sorted(b["mine"], key=lambda a: (1 if a.get("extra") else 0,
                                                                  a.get("id") or ""))],
        })
    rows.sort(key=lambda r: r["label"])
    n = len(rows)
    submitted = len([r for r in rows if r["files"] or r.get("pruned")])
    rated = len([r for r in rows if r["v"] is not None and r["v"] >= 1])
    todo = len([r for r in rows if r["files"] and not (r["v"] is not None and r["v"] >= 1)])
    missing = len([r for r in rows if not r["files"] and not r.get("pruned") and not (r["v"] is not None and r["v"] >= 1)])
    return rows, {"n": n, "submitted": submitted, "rated": rated, "todo": todo, "missing": missing}


def today_of(now=None):
    return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))


def rated_today(rows, now=None):
    """その回で、今日つけた評価の数（「今日おわったもの」に出す）。"""
    t0 = time.mktime(time.strptime(today_of(now), "%Y-%m-%d"))
    return len([1 for r in rows if (r.get("ratedAt") or 0) >= t0])


# ------------------------------------------------------------------
# 提案
# ------------------------------------------------------------------
def _first_paper(items, extra=False):
    ps = [a for a in items if (a.get("route") or "app") == "paper" and bool(a.get("extra")) == extra]
    ps.sort(key=lambda a: a.get("id") or "")
    return ps[0] if ps else None


def teacher_weights(log, by):
    """講師が出した／見送った数から、提案の種類ごとの重み（0〜1）。"""
    a, d = {}, {}
    for e in log or []:
        if e.get("by") != by:
            continue
        k = e.get("kind")
        if e.get("action") == "accept":
            a[k] = a.get(k, 0) + 1
        elif e.get("action") == "dismiss":
            d[k] = d.get(k, 0) + 1
    return {k: (a.get(k, 0) + 1.0) / (a.get(k, 0) + d.get(k, 0) + 2.0) for k in KIND_WORD}


def dismissed(log, sid, n, kind, now=None):
    t0 = (now or time.time()) - DISMISS_DAYS * 86400
    return any(e.get("sid") == sid and e.get("n") == n and e.get("kind") == kind
               and e.get("action") == "dismiss" and (e.get("at") or 0) >= t0
               for e in log or [])


def utext(u):
    """単元の呼び名と名前（lessons.unit_text と同じ決まり。insight は lessons を読まないのでここに置く）。"""
    lb = u.get("label")
    lb = str(lb) if lb is not None else ("第%d回" % int(u.get("n") or 0))
    return " ".join(x for x in (lb, str(u.get("topic") or "")) if x)


def suggest(ctx, matrix, sid, n, next_n, by, log=None, weekly=None, unit_items=0, now=None, names=None):
    """黄色の単元を押したときの提案。上から順に講師に見せる。

    next_n   次に出す回（決まりはこの回から効く）
    weekly   コースの毎週の分 [{"id","text","source"}]
    unit_items  その単元名が合うアプリの問題の数
    """
    stu = [s for s in matrix["students"] if s["sid"] == sid]
    if not stu:
        return []
    stu = stu[0]
    cell = stu["cells"].get(n) or {}
    u = cell.get("u")
    by_n = lesson_bundles(ctx.get("asgs"))
    mine = student_bundle(by_n.get(n) or [], sid)["mine"]
    topic = ""
    def nm(k):
        v = (names or {}).get(k)
        return v if v else ("第%d回" % k)
    this = {"n": n, "topic": ""}
    for x in matrix["units"]:
        if x["n"] == n:
            topic = x["topic"]
            this = x
    why = "%s の理解度 %s" % (utext(this), ("%d%%" % u) if u is not None else "―")
    ev = cell.get("ev") or {}
    parts = []
    if ev.get("hw") is not None:
        parts.append(("宿題 仮に%s（未評価）" % ratescale.LEVELS.get(PROVISIONAL_V, "")) if cell.get("prov")
                     else ("宿題 %s" % ratescale.LEVELS.get(cell.get("v"), "")))
    if ev.get("test") is not None:
        parts.append("テスト %d%%" % ev["test"])
    if ev.get("daily") is not None:
        parts.append("毎日テスト %d%%" % ev["daily"])
    if parts:
        why += "（" + "・".join(parts) + "）"

    out = []
    # 「解き直し」は提案しない（2026-09-11 本人：50%以下に解き直しを決め打ちするのは指示に反する）。
    # 足す宿題は講師のプリセット（presets.py）から選ぶ。ここが出すのは、
    # アプリの復習（その単元の問題）と、提出が続かない子の量の調整だけ。
    if u is not None and u < YELLOW and unit_items >= 5 and topic:
        cnt = 10 if unit_items >= 10 else unit_items
        out.append({"kind": "app", "why": why,
                    "title": "%s の復習 %d問（アプリ）" % (topic, cnt),
                    "span": "%sの宿題に足す（この回だけ）" % nm(next_n),
                    "rule": {"kind": "add", "until": "once", "from": next_n,
                             "with": {"text": "%s の復習 %d問" % (topic, cnt),
                                      "app": {"unit": topic, "count": cnt}},
                             "origin": {"kind": "app", "n": n}}})
    if (stu.get("missed") or 0) >= 3 and weekly:
        w = weekly[0]
        out.append({"kind": "lighten",
                    "why": "直近の宿題で %d回 提出がありません" % stu["missed"],
                    "title": "%s を半分に" % (w.get("text") or "毎週の分"),
                    "span": "%sから、次に変えるまで" % nm(next_n),
                    "rule": {"kind": "scale", "factor": 0.5, "until": None, "from": next_n,
                             "match": {"source": w.get("source") or "",
                                       "text": PR.base_text(w.get("text") or "")},
                             "origin": {"kind": "lighten", "n": n}}})
    wt = teacher_weights(log, by)
    base_rank = {"app": 2, "lighten": 1}
    out = [x for x in out if not dismissed(log, sid, n, x["kind"], now)]
    out.sort(key=lambda x: -(base_rank.get(x["kind"], 0) * (0.5 + wt.get(x["kind"], 0.5))))
    return out

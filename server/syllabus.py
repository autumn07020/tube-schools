#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教材の単元の並び（シラバス）―― 授業計画の「何を」の元。

なぜ別に置くか
--------------
授業計画（lessons.json）は「いつ・何を・宿題は何か」を持つ。これまで「何を」は
デモの組み立てが、アプリの教材の中の単元名を回して作っていた。本物の
カリキュラム（本部の週別の表）や教材の目次が届いたとき、差し込む口が無かった。

シラバスは **1本の教材の流れ** だけを持つデータにする。
  - 単元の並び（順番そのものが意味を持つ）
  - 教材での呼び名 label（第3回／5章-3／例題56-57。無い教材は空）
  - 総復習の回か review（**教材が決める。暦では決めない**）
  - どの週にどの単元をやったか anchor ―― 1点だけで日付に結びつける
  - 仮置きか provisional と、出どころ source

コースは `syllabus`（id）でシラバスを指す。授業計画はシラバスとコースの授業日から
組み立てる。本物が届いたら、同じ id で取り込み（save）、組み立て直すだけでよい
（出した宿題の記録は lessons.set_plan が残す）。

置き場（優先の順）
------
  <ROOT>/shared/syllabus/<id>.json     本部・教材から取り込んだもの（**いちばん優先**。手で直したいとき）
  カリキュラム/カリキュラム.json        原本（本部の表＋ロンドンの日程表。london.syllabi。curriculum_source.py）
  server/syllabus/<id>.json            コードと一緒に配る仮置き（原本に無いものだけ。2026-10-08 に12本を外した）

  原本のシラバスは perWeek（1回＝1週）で、単元ごとに week（その週の月曜）を持つ。
  schedule はその週の授業日に置く。授業の無い週（休校・ハーフターム・冬期講習会）は dates_of の skip で飛ぶ。

形
--
  {"id": "e4a-math", "name": "小4α 算数", "grade": "e4", "subject": "math",
   "materials": ["yos-e4-math"], "provisional": true, "source": "…",
   "anchor": {"unit": "第3回", "week": "2026-09-07"},
   "units": [{"label": "第1回", "topic": "比の基本"},
             {"label": "第5回", "topic": "総復習", "review": true}, …]}

  anchor.unit は units の呼び名（label、無ければ topic）で引く。重なっていてはいけない。
  anchor.week はその単元をやった週の **月曜**。
  単元1つが授業1回。週2回のコースは、1週に単元が2つ進む（例題56-57 と 例題58-59）。
"""
import datetime as _dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                    # noqa: E402
import curriculum_source as SOURCE              # noqa: E402

SEED_DIR = os.path.join(HERE, "syllabus")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LABEL_MAX, TOPIC_MAX = 24, 60


def _date(s):
    return _dt.date(*map(int, s.split("-")))


def unit_name(u):
    """教材での呼び名。無ければ単元名。"""
    return (str(u.get("label") or "") or str(u.get("topic") or "")).strip()


def problems(d):
    """形の誤り（空なら正しい）。取り込むとき・読むときに必ず通す。"""
    if not isinstance(d, dict):
        return ["シラバスが表（dict）ではありません"]
    out = []
    if not ID_RE.match(str(d.get("id") or "")):
        out.append("id は英小文字・数字・ハイフン（2〜40字）")
    units = d.get("units")
    if not isinstance(units, list) or not units:
        out.append("units（単元の並び）がありません")
        units = []
    names = []
    for i, u in enumerate(units):
        if not isinstance(u, dict):
            out.append("units[%d] が表ではありません" % i)
            continue
        t, lb = str(u.get("topic") or "").strip(), str(u.get("label") or "").strip()
        if not t:
            out.append("units[%d] に topic（単元名）がありません" % i)
        if len(t) > TOPIC_MAX or len(lb) > LABEL_MAX:
            out.append("units[%d] の名前が長すぎます" % i)
        if "review" in u and not isinstance(u["review"], bool):
            out.append("units[%d].review は true か false" % i)
        names.append(unit_name(u))
    a = d.get("anchor") if isinstance(d.get("anchor"), dict) else {}
    wk = str(a.get("week") or "")
    if not DATE_RE.match(wk):
        out.append("anchor.week（その単元をやった週の月曜）がありません")
    else:
        try:
            if _date(wk).weekday() != 0:
                out.append("anchor.week は月曜の日付にしてください")
        except ValueError:
            out.append("anchor.week が日付ではありません")
    au = str(a.get("unit") or "")
    if au not in names:
        out.append("anchor.unit が units の中にありません")
    elif names.count(au) > 1:
        out.append("anchor.unit と同じ呼び名が units に2つ以上あります")
    return out


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load(sid):
    """取り込んだもの（shared）を優先し、無ければ仮置き。形が崩れていれば None（使わない）。"""
    if not ID_RE.match(str(sid or "")):
        return None
    try:
        got = paths.load(paths.shared_file("syllabus", sid + ".json"), None)
    except paths.BadPath:
        got = None
    if got is None:
        got = SOURCE.syllabus(sid)
    if got is None:
        got = _read(os.path.join(SEED_DIR, sid + ".json"))
    if got is None or problems(got):
        return None
    return got


def default_id(key):
    """コース（クラス:教科）に原本が対応づけたシラバスの id。無ければ ""。"""
    return SOURCE.course_syllabus_id(key)


def of_course(key, p):
    """コースのシラバス。計画に syllabus が入っていて読めればそれ、無ければ（外した仮置きの id など）原本の対応。"""
    return load((p or {}).get("syllabus") or "") or load(default_id(key))


def save(d):
    """本部・教材から取り込んだシラバスを置く（同じ id は置き換え）。形が崩れていれば置かない。"""
    errs = problems(d)
    if errs:
        raise ValueError(" / ".join(errs))
    path = paths.shared_file("syllabus", d["id"] + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    paths.save(path, d)


def seeds():
    """原本の id と、コードと一緒に配る仮置きの id。"""
    ids = set(SOURCE.syllabus_ids())
    try:
        ids |= {f[:-5] for f in os.listdir(SEED_DIR) if f.endswith(".json")}
    except OSError:
        pass
    return sorted(ids)


def schedule(d, dates_of):
    """単元ごとの授業日 [(日付, 単元の番号)]。

    dates_of(start, count) … コースの授業日を start から count 個返す（courses.dates を包む）。
    anchor の週の **最初の授業日** に anchor の単元を置き、前後は授業1回に単元1つずつ並べる。
    anchor の週に授業が無い（休み）ときは、どこにも結びつけられないので空を返す。
    """
    units = d["units"]
    if d.get("perWeek") and all(DATE_RE.match(str(u.get("week") or "")) for u in units):
        return _schedule_weeks(units, dates_of)
    names = [unit_name(u) for u in units]
    ai = names.index(str(d["anchor"]["unit"]))
    mon = _date(d["anchor"]["week"])
    back = mon - _dt.timedelta(days=7 * (ai + 2))
    days = dates_of(back.isoformat(), 2 * (ai + len(units) + 8))
    i0 = next((i for i, x in enumerate(days) if x >= mon.isoformat()), None)
    if i0 is None or days[i0] >= (mon + _dt.timedelta(days=7)).isoformat() or i0 - ai < 0:
        return []
    return [(days[i0 - ai + j], j) for j in range(len(units)) if i0 - ai + j < len(days)]


def _schedule_weeks(units, dates_of):
    """week（月曜）を持つ単元を、その週の授業日に置く。同じ週に2つあれば1つ目・2つ目の授業日。
    その週に授業が無ければ（休みの週）その単元は置かない ―― 嘘の日付を作らない。"""
    out = []
    k = {}
    for j, u in enumerate(units):
        wk = str(u["week"])
        end = (_date(wk) + _dt.timedelta(days=6)).isoformat()
        days = [x for x in dates_of(wk, 7) if x <= end]
        i = k.get(wk, 0)
        k[wk] = i + 1
        if i < len(days):
            out.append((days[i], j))
    return out


def cycle_start(d, sched):
    """総復習の周期の起点（第1週の月曜）。教材の最初の総復習が第5週に来るように決める。無ければ None。"""
    for day, j in sched:
        if d["units"][j].get("review"):
            w = _date(day)
            w -= _dt.timedelta(days=w.weekday())
            return (w - _dt.timedelta(days=28)).isoformat()
    return None


def _monday(day):
    x = _date(day)
    return (x - _dt.timedelta(days=x.weekday())).isoformat()


def lesson_rows(d, sched, lesson_dates):
    """授業日ごとの計画の行。その週の単元を、その週の授業に順に当てる。

    原本は1週に1単元（数学3T は2単元）。ロンドンのコースは週2コマのこともある。
    週に単元が1つで授業が2回なら、2回ともその単元（**単元を2つ先へ詰めない**）。
    単元の無い週の授業日は行にしない（休みの週。呼ぶ側が skip に入れる）。"""
    by_week = {}
    for day, j in sched:
        by_week.setdefault(_monday(day), []).append(j)
    out, used = [], {}
    for x in lesson_dates:
        wk = _monday(x)
        js = by_week.get(wk)
        if not js:
            continue
        i = used.get(wk, 0)
        used[wk] = i + 1
        j = js[min(i, len(js) - 1)]
        u = d["units"][j]
        out.append({"date": x, "unit": j,
                    "label": str(u.get("label") or "").strip()[:LABEL_MAX],
                    "topic": str(u.get("topic") or "").strip()[:TOPIC_MAX],
                    "review": bool(u.get("review"))})
    return out


def rows(d, sched):
    """授業計画の行（lessons.set_plan に渡す形）。宿題はコースが決めるので入れない。"""
    out = []
    for day, j in sched:
        u = d["units"][j]
        out.append({"date": day, "unit": j,
                    "label": str(u.get("label") or "").strip()[:LABEL_MAX],
                    "topic": str(u.get("topic") or "").strip()[:TOPIC_MAX],
                    "review": bool(u.get("review"))})
    return out


def pace(d, sched, lessons, today, linked=True):
    """教材の予定に対して、コースがどこまで来ているか（単元の数で数える。総復習は数えない）。

      予定 … シラバスの予定日が today 以前の単元
      実施 … 授業計画で、日付が today 以前の回に入っている単元（「ずらす」と日付が動く）
      delta ＝ 実施 − 予定（マイナスは遅れ）
    """
    units = d["units"]

    def content(j):
        return 0 <= j < len(units) and not units[j].get("review")

    # 計画がこのシラバスから組まれていない（講師が画面で作った計画）ときは、行の呼び名か単元名で突き合わせる。
    # 1つも合わなければ、差を数えない ―― 結びついていない計画を「全部遅れ」と見せるのは嘘になる。
    if linked:
        def unit_of(l):
            j = l.get("unit")
            return j if isinstance(j, int) and not isinstance(j, bool) else None
    else:
        names = {}
        for j, u in enumerate(units):
            for nm in (str(u.get("label") or "").strip(), str(u.get("topic") or "").strip()):
                if nm and nm not in names:
                    names[nm] = j

        def unit_of(l):
            for nm in (str(l.get("label") or "").strip(), str(l.get("topic") or "").strip()):
                if nm in names:
                    return names[nm]
            return None
    exp = sorted({j for day, j in sched if day <= today and content(j)})
    done = sorted({unit_of(l) for l in (lessons or [])
                   if unit_of(l) is not None and content(unit_of(l))
                   and (l.get("date") or "") and l["date"] <= today})

    def show(j):
        u = units[j]
        return {"label": str(u.get("label") or ""), "topic": str(u.get("topic") or "")}

    # 単元の列（画面の点の並び）。今週の単元を中心に、前3つ・後2つ。総復習は入れない。
    #   state  done … 今日までに授業計画に入っている ／ late … 予定日が過ぎたのに入っていない ／ todo … まだ
    #   now    今週の単元（今週に無ければ、予定の最後の単元）  ahead … 予定より先に済んだ
    mon = _date(today) - _dt.timedelta(days=_date(today).weekday())
    wk = (mon.isoformat(), (mon + _dt.timedelta(days=6)).isoformat())
    order = [j for day, j in sched if content(j)]
    this_week = [j for day, j in sched if content(j) and wk[0] <= day <= wk[1]]
    cur = this_week[0] if this_week else (exp[-1] if exp else (order[0] if order else None))
    rail = []
    if cur is not None:
        k = order.index(cur)
        for j in order[max(0, k - 3): k + 3]:
            rail.append(dict(show(j), state=("done" if j in done else ("late" if j in exp else "todo")),
                             now=(j == cur), ahead=(j in done and j not in exp)))
    nxt = next((j for day, j in sched if day > today and content(j)), None)
    if not linked and not any(unit_of(l) is not None for l in (lessons or [])):
        return {"status": "unlinked", "current": show(cur) if cur is not None else None,
                "next": show(nxt) if nxt is not None else None,
                "provisional": bool(d.get("provisional")), "source": str(d.get("source") or ""),
                "alignment": str(d.get("alignment") or ""), "syllabus": d["id"]}
    return {"status": "ok", "delta": len(done) - len(exp), "expected": len(exp), "done": len(done),
            "missing": [show(j) for j in exp if j not in done],
            "extra": [show(j) for j in done if j not in exp],
            "next": show(nxt) if nxt is not None else None,
            "rail": rail, "current": show(cur) if cur is not None else None,
            "provisional": bool(d.get("provisional")), "source": str(d.get("source") or ""),
            "alignment": str(d.get("alignment") or ""),
            "syllabus": d["id"]}

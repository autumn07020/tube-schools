#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""使われなくなった口座の破棄（毎日の片づけ）。

何のためか
----------
塾は ID と名前を結ばない（設計-初回登録と匿名の口座.md）。だから「この子は退塾した」を
塾の側から口座に伝える道が無い。代わりに **使われなくなったこと** で見分ける：

    3か月（IDLE_DAYS 日）使われていない生徒の口座は、記録ごと全部消す。ID は空きに戻る。
    残すのは **ID を外した数字だけ**（retired.jsonl。学習の進み方を調べるためのもの）。

「使った」は、入口から入った日と、入ったままの画面で何かを開いた日（account の used。1日に1回だけ書く）。

消すもの（erase）
-----------------
  口座（accounts.json）・入ったままの印（tokens）・ID の索引
  アプリの記録（progress/）・講師むけの要約（summary/）
  出した写真と PDF（submissions/ と目録）・紙の評価（ratings.json）
  塾内テストの点（scores.json）・落とした単元（weak.json）
  特筆事項（notes.json）・宿題の決まり（personal.json）・連絡（messages.json）
  宿題の受け取り手（assignments.json の students。0人になる宿題は宿題ごと）・コースの指名

残すもの（numbers）
-------------------
  1人につき1行。**ID・sid・時刻・文章・写真は入れない。** 入るのは：
  消した月／学年／クラスの記号／受講科目／使っていた週の数／
  宿題の評価（教科・回・講師の評価・本人の評価）／テストの点（教科・種類・満点・得点）／
  落とした単元（教科・単元・回数）／アプリの数（解いた数・正解の数など）
  少人数のクラスなので「だれのものか絶対に戻せない」とまでは言えない（SECURITY.md に書いてある）。

動くのは **本番に切り替えた校舎だけ**（school.json の live）。デモ校と試し運用では何も消さない。

学年の繰り上げ（roll）
----------------------
年度のはじまりはデータに無いので、**管理者が入れた日付を読む**（exams.json の yearStart。推測しない）。
その日になったら1回だけ、在籍の生徒の学年を1つ上げる：
  ・同じ記号のクラスへ（小4α → 小5α）。行き先の学年にクラスが1つだけなら、そこへ。
  ・小6 → 中1 は記号が変わる（α・β・K → T・R・D）ので、クラスを空にして本人に聞く（needClass。ホームの札）。
  ・中3 は卒業（grad）。クラスから外れ、新しい宿題は届かない。記録は見られ、使わなくなって3か月で消える。
宿題の受け取り手は動かさない（出した時点で決まっている。前の学年で出た宿題は、受け取った本人のもの）。
前のクラスは acc["moves"] に残す（前のクラスの成績の表から、出ていった生徒として外れる）。
1年に1回だけ（ROLL_GAP）。日付を入れ直しても、繰り上げずみの年には動かない。
"""
import json
import os
import time

import paths
import exams as EX

DAY = 86400
IDLE_DAYS = 92                    # 3か月
SOON_DAYS = 14                    # 管理ページに「もうすぐ消える」と出す幅
KEEP_FILE = "retired.jsonl"
APP_KEYS = ("n", "mature", "stuck", "answered", "correct", "touched", "rated", "low")


def last_used(a, floor=0):
    """最後に使った時刻。印が無い口座は、合言葉を作った時刻・作られた時刻。floor（本番に切り替えた時刻）より前にはしない。"""
    return max(int(a.get("used") or a.get("pwAt") or a.get("created") or 0), int(floor or 0))


def _floor(T, school):
    meta = T.school_meta(school)
    return (int(meta.get("liveAt") or 0), bool(meta.get("live")))


def idle_rows(T, school, now=None, db=None):
    """生徒の口座と、使っていない日数。[(login_id, account, days)]。日数の多い順。本番でない校舎は空。"""
    now = now or time.time()
    floor, live = _floor(T, school)
    if not live:
        return []
    db = T.accounts(school) if db is None else db
    rows = [(lid, a, int((now - last_used(a, floor)) // DAY))
            for lid, a in db.items() if a.get("role") == "student" and a.get("sid")]
    rows.sort(key=lambda r: (-r[2], r[0]))
    return rows


def view(T, school, db=None, now=None):
    """管理ページむけ：もうすぐ消える口座の数（SOON_DAYS 日以内）と、これまでに消した数。"""
    rows = idle_rows(T, school, now, db)
    soon = [{"id": lid, "days": d, "left": max(0, IDLE_DAYS - d)} for lid, _a, d in rows if d >= IDLE_DAYS - SOON_DAYS]
    return {"idleDays": IDLE_DAYS, "soon": soon[:50], "gone": _count_kept(school)}


def _keep_path(school):
    return os.path.join(paths.school_dir(school), KEEP_FILE)


def _count_kept(school):
    try:
        with open(_keep_path(school), "rb") as f:
            return sum(1 for _ in f)
    except (OSError, paths.BadPath):
        return 0


def numbers(T, school, a, now=None):
    """この生徒の、ID を外した数字。**ID・sid・時刻・文章は入れない。**"""
    now = now or time.time()
    sid = a.get("sid")
    asg = T.assignments(school)
    hw = []
    for aid, per in (T.ratings(school) or {}).items():
        r = (per or {}).get(sid)
        if not isinstance(r, dict):
            continue
        x = asg.get(aid) or {}
        hw.append([x.get("subject") or "", (x.get("lesson") or {}).get("n"), r.get("v"), r.get("s")])
    tests = []
    for t in (T.SCORES.load(school).get("tests") or {}).values():
        row = (t.get("rows") or {}).get(sid)
        if row is None:
            continue
        tests.append({"subject": str(t.get("key") or "").split(":")[-1], "kind": t.get("kind") or "",
                      "max": [c.get("max") for c in (t.get("cols") or [])], "got": row})
    wk = {}
    for sub, v in ((T.weak.load(school) or {}).get(sid) or {}).items():
        units = (v or {}).get("units") or {}
        wk[sub] = [[name, u.get("w"), u.get("n")] for name, u in units.items() if isinstance(u, dict)]
    try:
        summ = paths.load(paths.summary_path(school, sid), None) or {}
    except paths.BadPath:
        summ = {}
    cid = str(a.get("classId") or "")
    grade = str(a.get("level") or "")
    since = int(a.get("created") or 0)
    return {"month": time.strftime("%Y-%m", time.localtime(now)), "grade": grade,
            "cls": cid[len(grade):] if grade and cid.startswith(grade) else "",
            "subjects": list(a.get("subjects") or []),
            "weeks": max(0, int((last_used(a) - since) // (7 * DAY))) if since else 0,
            "hw": hw, "tests": tests, "weak": wk,
            "app": {k: summ.get(k) for k in APP_KEYS if isinstance(summ.get(k), (int, float))}}


def erase_records(T, school, sid):
    """この生徒の記録（口座以外）を全部消す。**戻せない。呼ぶ側で LOCK を持つこと。**

    退塾の整理（erase）と、ためし運用のデモの片づけ（demo_trial.py --clean。口座は残す）が同じここを通る。
    """
    try:
        os.remove(paths.progress_path(school, sid))
    except (OSError, paths.BadPath):
        pass
    T.drop_summary(school, sid)
    for drop in (T.SUB.drop_student, T.NOTES.drop_student, T.PERSONAL.drop_student,
                 T.SCORES.drop_student, T.MESSAGES.drop_student):
        try:
            drop(school, sid)             # 写真は、進捗より重い個人情報。手書きの字も名前も写っている
        except (OSError, paths.BadPath):
            pass
    try:
        wdb = T.weak.load(school)
        if sid in wdb:
            wdb.pop(sid, None)
            T.weak.save(school, wdb)
    except (OSError, paths.BadPath):
        pass
    rdb = T.ratings(school)
    hit = False
    for aid in list(rdb):
        if sid in (rdb[aid] or {}):
            rdb[aid].pop(sid, None)
            hit = True
        if not rdb[aid]:
            rdb.pop(aid)
            hit = True
    if hit:
        T.save_ratings(school, rdb)
    # 宿題の受け取り手から外す。0人になる宿題は、宿題ごと消す（students が空の宿題は「クラス全員」に化ける）。
    asg = T.assignments(school)
    hit = False
    for aid in list(asg):
        x = asg[aid]
        if not isinstance(x, dict) or sid not in (x.get("students") or []):
            continue
        x["students"] = [s for s in x["students"] if s != sid]
        if x.get("joined"):
            x["joined"] = [j for j in x["joined"] if j.get("sid") != sid]
            if not x["joined"]:
                x.pop("joined")
        if not x["students"]:
            asg.pop(aid)
        hit = True
    if hit:
        T.save_assignments(school, asg)
    # コースの指名と、上乗せの組からも外す。指名が0人になるコースは、そのままにする
    # （空の指名は「クラス全員」の意味に変わってしまう。口座の無い sid は、だれも指さない）。
    try:
        ls = T.lessons.load(school)
        hit = False
        for p in (ls.get("plans") or {}).values():
            if not isinstance(p, dict):
                continue
            st = p.get("students") or []
            if sid in st and len(st) > 1:
                p["students"] = [s for s in st if s != sid]
                hit = True
            for ex in (p.get("extra") or []):
                if isinstance(ex, dict) and sid in (ex.get("students") or []):
                    ex["students"] = [s for s in ex["students"] if s != sid]
                    hit = True
        if hit:
            T.lessons.save(school, ls)
    except (OSError, paths.BadPath):
        pass


def erase(T, school, lid, a, db):
    """この生徒の記録を、全部消す。**戻せない。呼ぶ側で LOCK を持つこと。** accounts の保存は呼ぶ側。

    退塾から6か月の整理（purge）と、3か月使われない口座の破棄（run）が、同じここを通る。
    """
    sid = a.get("sid")
    if sid:
        erase_records(T, school, sid)
    T.revoke_tokens(lid)
    db.pop(lid, None)
    paths.unbind_login(lid)


def run(T, school, now=None, dry=False):
    """3か月使われていない生徒の口座を破棄する。消した（dry なら、消すはずの）ID の一覧を返す。"""
    now = now or time.time()
    with T.LOCK:
        db = T.accounts(school)
        due = [(lid, a, d) for lid, a, d in idle_rows(T, school, now, db) if d >= IDLE_DAYS]
        if dry or not due:
            return [lid for lid, _a, _d in due]
        lines = [json.dumps(numbers(T, school, a, now), ensure_ascii=False, sort_keys=True) for _lid, a, _d in due]
        with open(_keep_path(school), "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        for lid, a, _d in due:
            erase(T, school, lid, a, db)
        T.save_accounts(school, db)
    for lid, _a, d in due:
        T.audit(school, "system", "retired", lid, "%d日 使われていない" % d)
    return [lid for lid, _a, _d in due]


# ------------------------------------------------------------------
# 学年の繰り上げ
# ------------------------------------------------------------------
NEXT_GRADE = {"e1": "e2", "e2": "e3", "e3": "e4", "e4": "e5", "e5": "e6", "e6": "j1", "j1": "j2", "j2": "j3", "j3": None}
ROLL_GAP = 300 * DAY              # 1年に1回だけ


def roll_due(T, school, now=None):
    """いま繰り上げる日か。繰り上げるなら、その日付（"YYYY-MM-DD"）。そうでなければ None。"""
    now = now or time.time()
    ys = EX.year_start(school)
    if not ys or time.strftime("%Y-%m-%d", time.localtime(now)) < ys:
        return None
    r = T.school_meta(school).get("rolled") or {}
    if r.get("date") == ys or now - int(r.get("at") or 0) < ROLL_GAP:
        return None
    return ys


def next_class(tbl, grade, class_id):
    """繰り上げたあとの (学年, クラス)。卒業は (None, "")。聞くときはクラスが ""。"""
    ng = NEXT_GRADE.get(grade)
    if ng is None:
        return None, ""
    there = [cid for cid, c in tbl.items() if (c.get("grade") or "") == ng]
    cand = ng + class_id[len(grade):] if class_id and class_id.startswith(grade) else ""
    if grade[0] == ng[0] and cand in there:
        return ng, cand                         # 同じ記号のクラスへ
    if len(there) == 1:
        return ng, there[0]                     # 行き先が1つしかない
    return ng, ""                               # 本人に聞く（小6→中1 は、記号が変わる）


def roll(T, school, now=None):
    """繰り上げる日なら、在籍の生徒の学年を1つ上げる。したら {date, up, grad, ask}、しなければ None。"""
    now = now or time.time()
    with T.LOCK:
        ys = roll_due(T, school, now)
        if not ys:
            return None
        tbl = T.class_table(school)
        db = T.accounts(school)
        up = grad = ask = 0
        for a in db.values():
            if a.get("role") != "student" or a.get("leftAt") or a.get("grad"):
                continue
            g, old = a.get("level") or "", a.get("classId") or ""
            if g not in NEXT_GRADE:
                continue
            ng, new = next_class(tbl, g, old)
            if ng is None:
                a["grad"] = ys
                grad += 1
            else:
                a["level"] = ng
                up += 1
                if new:
                    a.pop("needClass", None)
                else:
                    a["needClass"] = ys
                    ask += 1
            if new != old:
                seat = T.seat_of(a)
                a.setdefault("moves", []).append({"at": int(now), "by": "year",
                                                  "from": {"classId": old, "seat": seat}, "to": {"classId": new, "seat": seat}})
            a["classId"] = new
        T.save_accounts(school, db)
        meta = dict(T.school_meta(school))
        meta["rolled"] = {"date": ys, "at": int(now), "up": up, "grad": grad, "ask": ask}
        paths.save(paths.school_file(school, "school.json"), meta)
    T.audit(school, "system", "rolled", "", "学年を上げた %d人・卒業 %d人・クラスを聞く %d人" % (up, grad, ask))
    return dict(meta["rolled"])

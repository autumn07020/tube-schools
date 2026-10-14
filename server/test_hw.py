#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""コースの宿題が、決めたとおりに出るかを確かめる。

なぜこの検査が要るか
--------------------
自動発行は講師の操作を待たずに動く。まちがって出ても、
画面には「出した」としか出ない。**誰に・何件・いつまでが正しいか**は
目で見ても分からないので、決めごとそのものを確かめる。

  ・1回に2ブロックなら宿題2件。ブロックごとに route と graded
  ・受け取り手は出した時点で書き込む。受講科目の無い教科の生徒は入らない
  ・あとで受講科目を変えても、出した宿題の受け取り手は変わらない
  ・上乗せ（上位）は指名の生徒にだけ
  ・毎週固定は週1回。何度呼んでも増えない。2500 の次は 1
  ・期限は次の回の授業開始（小5β は次の月曜、中3 は次の授業）
  ・0人のコースは出さない
  ・前回の提出状況は、同じ回のブロックを束ねて数える

    python3 server/test_hw.py
"""

import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-hw"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["TZ"] = "Europe/London"
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import lessons as L                              # noqa: E402
import courses as C                              # noqa: E402
import tube_server as T                          # noqa: E402

SCHOOL = "london"
ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


def at(text):
    """「2026-09-17 20:00」→ 時刻（秒）"""
    return time.mktime(time.strptime(text, "%Y-%m-%d %H:%M"))


def hm(ms):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ms / 1000.0))


def sid(lid):
    return T.accounts(SCHOOL)[lid]["sid"]


def setup():
    paths.ensure_school(SCHOOL)
    paths.save(paths.school_file(SCHOOL, "school.json"),
               {"id": SCHOOL, "name": "検査校", "code": "l", "tz": "Europe/London"})
    paths.save(paths.school_file(SCHOOL, "curriculum.json"), {"v": 2, "classes": [
        {"id": c, "name": c, "grade": c[:2]} for c in ("e5b", "j2t", "j2r", "j2d", "j3r")]})
    paths.save(paths.school_file(SCHOOL, "materials.json"), {"items": {
        "sirius-j2": {"name": "Sirius21 中2", "subject": "english", "mode": "paper"},
        "jack21": {"name": "Jack21", "subject": "english", "mode": "paper"},
        "grit2500": {"name": "Vocabulary GRIT 2500", "subject": "english",
                     "mode": "paper", "graded": False},
        "yos-e5-math": {"name": "予習シリーズ 小5下 算数", "subject": "math", "mode": "paper"},
        "enshu-e5-math": {"name": "演習問題集 小5下 算数", "subject": "math", "mode": "paper"},
        "kiso-print": {"name": "基礎力強化プリント", "subject": "math", "mode": "paper"},
        "keisan-yos": {"name": "計算テキスト（予習シリーズ）", "subject": "math",
                       "mode": "paper", "graded": False},
        "joui-reg": {"name": "上位校の数学 レギュラー", "subject": "math", "mode": "paper"}}})
    for lid, seat, cid, subs in [
            ("lj2t01", "01", "j2t", "国数英理社"), ("lj2t02", "02", "j2t", "国英"),
            ("lj2r01", "01", "j2r", "国数英"), ("lj2r02", "02", "j2r", "国数英理社"),
            ("lj2r03", "03", "j2r", None),
            ("lj2d01", "01", "j2d", "国数"), ("lj2d02", "02", "j2d", "国数英理社"),
            ("le5b01", "01", "e5b", "国数英理社"), ("le5b02", "02", "e5b", "国数"),
            ("le5b03", "03", "e5b", "国数英"),
            ("lj3r01", "01", "j3r", "国数英"), ("lj3r02", "02", "j3r", "国数英"),
            ("lj3r03", "03", "j3r", "国数英")]:
        T.add_account(SCHOOL, lid, "student-pass", seat, "student", cid[:2], cid,
                      subjects=C.parse_subjects(subs) if subs else None)
    T.add_account(SCHOOL, "t-a", "t-a-pass", "T1", "teacher", "j2", "j2r", classes=["j2r"])
    db = T.accounts(SCHOOL)
    db["t-a"]["assign"] = []
    T.save_accounts(SCHOOL, db)
    ta = sid("t-a")

    def slot(day, start, end):
        return {"day": day, "start": start, "end": end}

    base = {"teachers": [ta], "unit": "lesson", "weekday": 0, "from": "", "to": "",
            "classes": [], "students": []}
    C.upsert(SCHOOL, [
        ("j2tr:english", dict(base, name="中2TR 英語", grade="j2", subject="english",
                              slots=[slot(2, "16:40", "18:10")], classes=["j2t", "j2r", "j2d"])),
        ("e5b:math", dict(base, name="小5β 算数", grade="e5", subject="math",
                          slots=[slot(1, "16:40", "18:10"), slot(4, "16:40", "18:10")],
                          classes=["e5b"], unit="week", weekday=1)),
        ("j3r:math", dict(base, name="中3R 数学", grade="j3", subject="math",
                          slots=[slot(2, "18:20", "19:50"), slot(4, "18:20", "19:50")],
                          classes=["j3r"])),
        ("j3doku:math", dict(base, name="中3 土特", grade="j3", subject="math",
                             slots=[slot(6, "16:00", "17:10")],
                             students=[sid("lj3r01"), sid("lj3r02")])),
        ("zero:math", dict(base, name="0人のコース", grade="j2", subject="math",
                           slots=[slot(1, "10:00", "11:00")])),
    ])

    def rows(n, items, extra=None):
        out = []
        for i in range(1, n + 1):
            r = {"topic": "第%d回" % i, "hw": {"items": [dict(x) for x in items]}}
            if extra:
                r["extraHw"] = extra
            out.append(r)
        return out

    L.set_plan(SCHOOL, "j2tr:english", ta, "", 0, "2026-09-14", rows(4, [
        {"text": "Sirius21 練成問題", "source": "sirius-j2", "from": 88, "to": 90},
        {"text": "Jack21 練成問題", "source": "jack21", "from": 52, "to": 55}]))
    L.set_plan(SCHOOL, "e5b:math", ta, "", 0, "2026-09-14", rows(3, [
        {"text": "予習シリーズ 基本問題", "source": "yos-e5-math", "from": 12, "to": 13},
        {"text": "演習問題集 基本問題＋トレーニング", "source": "enshu-e5-math", "from": 20, "to": 23}]))
    L.set_plan(SCHOOL, "j3r:math", ta, "", 0, "2026-09-14", rows(4, [
        {"text": "レギュラー 例題3題", "source": "joui-reg", "from": 60, "to": 62}]))
    L.set_plan(SCHOOL, "j3doku:math", ta, "", 0, "2026-09-12", rows(2, [
        {"text": "レギュラー 例題（復習）", "source": "joui-reg", "from": 57, "to": 59}]))
    L.set_plan(SCHOOL, "zero:math", ta, "", 0, "2026-09-14", rows(2, [
        {"text": "問題集 p.1-2"}]))
    # 上乗せと毎週固定は、定義の欄ではなく計画の欄に入れる（CSV では入らない）
    with L.paths_lock():
        data = L.load(SCHOOL)
        e5 = data["plans"]["e5b:math"]
        e5["extra"] = [{"id": "top", "name": "上位", "students": [sid("le5b01")]}]
        e5["weekly"] = [{"id": "keisan", "text": "計算テキスト", "source": "keisan-yos",
                         "step": 7, "at": 0, "wrap": 0}]
        for l in e5["lessons"]:
            l["extraHw"] = {"top": {"items": [
                {"text": "基礎力強化プリント", "source": "kiso-print", "from": 1, "to": 4}]}}
        en = data["plans"]["j2tr:english"]
        en["weekly"] = [{"id": "grit", "text": "GRIT 100単語＋連語25語", "source": "grit2500",
                         "step": 125, "at": 2375, "wrap": 2500}]
        # 範囲も教材も無い、文だけのブロック（紙として出る）
        data["plans"]["j3r:math"]["lessons"][0]["hw"]["items"].append({"text": "計算の復習プリント"})
        L.save(SCHOOL, data)


def hw_of(key, n=None):
    return [a for a in T.assignments(SCHOOL).values()
            if (a.get("lesson") or {}).get("key") == key
            and (n is None or (a.get("lesson") or {}).get("n") == n)]


def main():
    setup()
    now = at("2026-09-17 20:00")          # 木曜の夜

    print("\n1回目の発行")
    made = T.publish_courses(SCHOOL, "test", now=now)
    check("発行した回がある", len(made) >= 4, made)

    en = hw_of("j2tr:english", 1)
    titles = sorted(a["title"] for a in en)
    check("中2英語の1回で3件（2ブロック＋毎週固定）", len(en) == 3, titles)
    by = {a["source"]: a for a in en}
    check("ブロックごとに route（紙）", all(a["route"] == "paper" for a in en))
    check("採点する教材は graded:true", by["sirius-j2"]["graded"] is True and by["jack21"]["graded"] is True)
    check("出すだけの教材（GRIT）は graded:false", by["grit2500"]["graded"] is False)
    check("GRIT の範囲は 2376〜2500", (by["grit2500"]["from"], by["grit2500"]["to"]) == (2376, 2500),
          (by["grit2500"]["from"], by["grit2500"]["to"]))
    want = sorted(sid(x) for x in ["lj2t01", "lj2t02", "lj2r01", "lj2r02", "lj2r03", "lj2d02"])
    check("受け取り手は英語を受講している生徒（受講科目の無い生徒は全教科）",
          sorted(by["sirius-j2"]["students"]) == want, len(by["sirius-j2"]["students"]))
    check("中2D の国数の生徒は入らない", sid("lj2d01") not in by["sirius-j2"]["students"])
    check("classId はコースID、教科は english",
          by["sirius-j2"]["classId"] == "j2tr" and by["sirius-j2"]["subject"] == "english")
    check("期限は次の回（9/22 火 16:40）", hm(by["sirius-j2"]["dueAt"]) == "2026-09-22 16:40",
          hm(by["sirius-j2"]["dueAt"]))
    ta = dict(T.accounts(SCHOOL)["t-a"], school=SCHOOL)
    check("担当の講師から見える", T.can_see(ta, "j2tr", "english"))
    les = [l for l in L.plan(SCHOOL, "j2tr:english")["lessons"] if l["n"] == 1][0]
    check("出した回に3件ぶんのIDが残る", len(les.get("publishedIds") or []) == 3, les.get("publishedIds"))

    e5 = hw_of("e5b:math", 1)
    check("小5β の1回で4件（2ブロック＋上位＋毎週固定）", len(e5) == 4, [a["title"] for a in e5])
    e5by = {a["source"]: a for a in e5}
    check("上位の分は、指名の生徒にだけ", e5by["kiso-print"]["students"] == [sid("le5b01")],
          e5by["kiso-print"]["students"])
    check("通常の分は3人全員（上乗せで消えない）", len(e5by["yos-e5-math"]["students"]) == 3)
    check("上乗せの分にだけ印（extra）が付く", e5by["kiso-print"].get("extra") == "top"
          and not e5by["yos-e5-math"].get("extra"))
    check("期限は次の月曜 16:40", hm(e5by["yos-e5-math"]["dueAt"]) == "2026-09-21 16:40",
          hm(e5by["yos-e5-math"]["dueAt"]))
    check("計算テキストは出すだけ・範囲 1〜7",
          e5by["keisan-yos"]["graded"] is False and
          (e5by["keisan-yos"]["from"], e5by["keisan-yos"]["to"]) == (1, 7))

    j3 = sorted(hw_of("j3r:math"), key=lambda a: (a["lesson"]["n"], a["title"]))
    ns = sorted({a["lesson"]["n"] for a in j3})
    check("中3R は火と木の2回が出る", ns == [1, 2], ns)
    first = [a for a in j3 if a["lesson"]["n"] == 1 and a["source"] == "joui-reg"][0]
    second = [a for a in j3 if a["lesson"]["n"] == 2 and a["source"] == "joui-reg"][0]
    check("火の回の期限は木 18:20", hm(first["dueAt"]) == "2026-09-17 18:20", hm(first["dueAt"]))
    check("木の回の期限は次の火 18:20", hm(second["dueAt"]) == "2026-09-22 18:20", hm(second["dueAt"]))
    plain = [a for a in j3 if a["title"] == "計算の復習プリント"]
    check("文だけのブロックも、紙の宿題として出る（番号なし）",
          len(plain) == 1 and plain[0]["route"] == "paper" and plain[0]["from"] == 0, plain)

    doku = hw_of("j3doku:math")
    check("土特は指名の2人だけ", len(doku) == 1 and sorted(doku[0]["students"]) ==
          sorted([sid("lj3r01"), sid("lj3r02")]), doku)
    check("0人のコースは出さない", hw_of("zero:math") == [])
    check("0人のコースの回には印を付けない（生徒が入ったら出せる）",
          not any(l.get("published") for l in L.plan(SCHOOL, "zero:math")["lessons"]))

    print("\n何度呼んでも増えない")
    n0 = len(T.assignments(SCHOOL))
    T.publish_courses(SCHOOL, "test", now=now)
    T.publish_courses(SCHOOL, "test", now=now + 3600)
    check("同じ日にもう2回呼んでも件数は同じ", len(T.assignments(SCHOOL)) == n0,
          (n0, len(T.assignments(SCHOOL))))
    en_plan = L.plan(SCHOOL, "j2tr:english")
    check("毎週固定の位置が1回分だけ進む", en_plan["weekly"][0]["at"] == 2500, en_plan["weekly"])

    print("\n出したあとで受講科目を変えても変わらない")
    db = T.accounts(SCHOOL)
    db["lj2t02"]["subjects"] = ["japanese"]
    T.save_accounts(SCHOOL, db)
    again = {a["source"]: a for a in hw_of("j2tr:english", 1)}
    check("出した宿題の受け取り手はそのまま", sid("lj2t02") in again["sirius-j2"]["students"])

    print("\n次の週")
    T.publish_courses(SCHOOL, "test", now=at("2026-09-22 20:00"))
    en2 = {a["source"]: a for a in hw_of("j2tr:english", 2)}
    check("GRIT は 2500 の次に 1 から", (en2["grit2500"]["from"], en2["grit2500"]["to"]) == (1, 125),
          (en2.get("grit2500") or {}).get("from"))
    check("受講科目を変えた生徒には、次の回から出ない", sid("lj2t02") not in en2["sirius-j2"]["students"])

    print("\n前回の提出状況（同じ回を束ねる）")
    ratings = {}
    sirius, jack = again["sirius-j2"], again["jack21"]
    for s in sirius["students"]:
        ratings.setdefault(sirius["id"], {})[s] = {"v": 3, "at": 1}
    for s in jack["students"][:3]:
        ratings.setdefault(jack["id"], {})[s] = {"v": 2, "at": 1}
    T.save_ratings(SCHOOL, ratings)
    asg = list(T.assignments(SCHOOL).values())
    pairs = T.Handler.grid_pairs(None, SCHOOL, asg, at("2026-09-23 12:00") * 1000)
    rec = pairs.get("j2tr|english") or {}
    last = rec.get("last") or {}
    check("前回は第1回の2ブロックを束ねた率（9/12 = 75%）", last.get("pct") == 75, last)
    check("出すだけの GRIT は数えない", "GRIT" not in (last.get("title") or ""), last)
    check("手が要る件数は、回で1件", rec.get("late") == 1, rec)

    cells = L.week_cells(SCHOOL, ["j3r:math", "e5b:math"], when=at("2026-09-17 20:00"))
    check("今週のマス: 中3R は火木とも出した", cells["j3r:math"]["state"] == "out", cells["j3r:math"])
    check("今週のマス: 小5β は月曜の回", (cells["e5b:math"]["cell"] or {}).get("date") == "2026-09-14",
          cells["e5b:math"])

    print()
    if ng_n:
        print("× %d件おちた" % ng_n)
        return 1
    print("すべて通った。（%d件）" % ok_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())

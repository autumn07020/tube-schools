#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""クラス替え（組み分けテストのたびに α⇄β・T⇄R）に耐えるかを確かめる。

なぜこの検査が要るか
--------------------
ロンドン校では組み分けテストのたびに（ほぼ毎月）、α と β、T と R の生徒が入れ替わる。
ログインIDは「校舎＋クラス＋番号」で作るので、何もしなければ
  ・移った生徒の前のクラスの記録が、本人の「成績の伸び」から消える
  ・テストの日の席で書かれた表を、今の席で合わせて別の生徒に点が入る
  ・前のクラスの成績の人数が、学期ごとに膨らむ
  ・空いた席に古い名簿を流し直すと、同じ「小4α-02」が2人になる
どれも画面の上では何も起きていないように見える。だから決めごとそのものを確かめる。

  ・move は確かめるだけが既定。--yes で移す。ログインID・sid・パスワード・記録は変わらない
  ・前の席は日付つきで残り、その日の席を引ける（class_at・desk_labels(at=)）
  ・期限の来ていない宿題：出ていくコースからは外す（記録があれば外さない）・入るコースには足す
  ・期限の過ぎた宿題・学年のコース・指名のコースは触らない
  ・前のクラスの成績の一覧に出ない。本人の成績の伸びには前のクラスの単元が残る
  ・前のコースの「個別の宿題」の一覧に、もう効かない決まりを出さない
  ・テストの表はテストの日の席で合わせる（今その席にいる別の生徒に入れない）
  ・同じ席に2人を作らない（move・roster-import・add）
  ・--undo で戻る。宿題の付け替えも戻る。あとで別のクラス替えがあれば、先に新しい方から

    python3 server/test_moves.py
"""

import argparse
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-moves"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["TZ"] = "Europe/London"
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import lessons as L                              # noqa: E402
import courses as C                              # noqa: E402
import personal as PR                            # noqa: E402
import ratescale                                 # noqa: E402
import scores as SC                              # noqa: E402
import submissions as SUB                        # noqa: E402
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
    return time.mktime(time.strptime(text, "%Y-%m-%d %H:%M"))


def sid(lid):
    return T.accounts(SCHOOL)[lid]["sid"]


def acc(lid):
    return T.accounts(SCHOOL)[lid]


def hw_of(key, n=None):
    return [a for a in T.assignments(SCHOOL).values()
            if (a.get("lesson") or {}).get("key") == key
            and (n is None or (a.get("lesson") or {}).get("n") == n)]


def csv(name, text):
    p = os.path.join(ROOT, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def setup():
    paths.ensure_school(SCHOOL)
    paths.save(paths.school_file(SCHOOL, "school.json"),
               {"id": SCHOOL, "name": "検査校", "code": "l", "tz": "Europe/London"})
    paths.save(paths.school_file(SCHOOL, "curriculum.json"), {"v": 2, "classes": [
        {"id": "e4a", "name": "小4α", "grade": "e4"}, {"id": "e4b", "name": "小4β", "grade": "e4"},
        {"id": "j2t", "name": "中2T", "grade": "j2"}]})
    paths.save(paths.school_file(SCHOOL, "materials.json"), {"items": {
        "yos-e4-math": {"name": "予習シリーズ 小4下 算数", "subject": "math", "mode": "paper"},
        "rika": {"name": "理科の問題集", "subject": "science", "mode": "paper"}}})
    for lid, seat, cid in [("le4a01", "01", "e4a"), ("le4a02", "02", "e4a"), ("le4a03", "03", "e4a"),
                           ("le4b01", "01", "e4b"), ("le4b02", "02", "e4b"), ("le4b03", "03", "e4b")]:
        T.add_account(SCHOOL, lid, "student-pass", seat, "student", "e4", cid)
    T.add_account(SCHOOL, "lj2t01", "student-pass", "01", "student", "j2", "j2t")
    T.add_account(SCHOOL, "t-a", "t-a-pass", "T1", "teacher", "e4", "e4a", classes=["e4a", "e4b"])
    ta = sid("t-a")

    def slot(day, start, end):
        return {"day": day, "start": start, "end": end}

    base = {"teachers": [ta], "unit": "lesson", "weekday": 0, "from": "", "to": "",
            "classes": [], "students": []}
    C.upsert(SCHOOL, [
        ("e4a:math", dict(base, name="小4α 算数", grade="e4", subject="math",
                          slots=[slot(3, "18:20", "19:50")], classes=["e4a"])),
        ("e4b:math", dict(base, name="小4β 算数", grade="e4", subject="math",
                          slots=[slot(4, "16:40", "18:10")], classes=["e4b"])),
        ("e4:science", dict(base, name="小4 理科", grade="e4", subject="science",
                            slots=[slot(5, "16:40", "17:40")], classes=["e4a", "e4b"])),
        ("e4o:math", dict(base, name="小4 オンライン 算数", grade="e4", subject="math",
                          slots=[slot(6, "10:00", "11:00")], students=[sid("le4a02")])),
    ])

    def rows(n, items):
        return [{"topic": "第%d回" % i, "hw": {"items": [dict(x) for x in items]}} for i in range(1, n + 1)]

    L.set_plan(SCHOOL, "e4a:math", ta, "", 0, "2026-09-09", rows(4, [
        {"text": "予習シリーズ 基本問題", "source": "yos-e4-math", "from": 10, "to": 11}]))
    L.set_plan(SCHOOL, "e4b:math", ta, "", 0, "2026-09-10", rows(4, [
        {"text": "予習シリーズ 基本問題", "source": "yos-e4-math", "from": 10, "to": 11}]))
    L.set_plan(SCHOOL, "e4:science", ta, "", 0, "2026-09-11", rows(4, [
        {"text": "理科の問題集", "source": "rika", "from": 1, "to": 2}]))
    L.set_plan(SCHOOL, "e4o:math", ta, "", 0, "2026-09-12", rows(4, [
        {"text": "オンラインの問題", "source": "yos-e4-math", "from": 1, "to": 2}]))
    return ta


def main():
    ta = setup()
    S, TT, U = "le4a02", "le4a03", "le4b01"          # S:α→β（記録あり） TT:α→β（記録なし） U:β→α
    sS, sT, sU = sid(S), sid(TT), sid(U)

    print("\n発行（9/10 と 9/17）")
    T.publish_courses(SCHOOL, "test", now=at("2026-09-10 20:00"))
    T.publish_courses(SCHOOL, "test", now=at("2026-09-17 20:00"))
    a1 = hw_of("e4a:math", 1)[0]
    a2 = hw_of("e4a:math", 2)[0]
    b2 = hw_of("e4b:math", 2)[0]
    check("α 第1回（期限 9/16）・第2回（期限 9/23）・β 第2回（期限 9/24）がある",
          a1 and a2 and b2, [len(hw_of("e4a:math")), len(hw_of("e4b:math"))])
    check("S は α の宿題の受け取り手", sS in a1["students"] and sS in a2["students"])
    # S は α 第1回・第2回に写真を出し、第1回に評価が付いている（記録）
    SUB.put(SCHOOL, a2["id"], sS, [{"kind": "jpg", "data": b"\xff\xd8\xff\xd9"}])
    rt = T.ratings(SCHOOL)
    rt.setdefault(a1["id"], {})[sS] = ratescale.record(4, ta, now=at("2026-09-16 20:00"))
    T.save_ratings(SCHOOL, rt)
    # α で S に個別の決まり（減らす）
    PR.put_rule(SCHOOL, "e4a:math", sS, {"kind": "drop", "match": {"source": "yos-e4-math"}}, ta, 3)
    check("移る前：α の「個別の宿題」に S が出る",
          any(r["sid"] == sS for r in T.desk_board(SCHOOL, "e4a:math", C.all_courses(SCHOOL)["e4a:math"])))

    print("\n確かめる（書かない）")
    t_move = at("2026-09-20 10:00")
    p = csv("bad-name.csv", "id,name,classId,seat\nle4a02,だれか,e4b,04\n")
    try:
        T.move_rows(SCHOOL, p)
        check("氏名の列を拒む", False)
    except ValueError:
        check("氏名の列を拒む", True)
    rows, bad = T.move_rows(SCHOOL, csv("dup.csv", "id,classId,seat\nle4a01,e4b,02\n"))
    plan, errors = T.move_plan(SCHOOL, rows, t_move)
    check("同じ席に2人になる移動は止める", errors and "重なります" in errors[0], errors)
    rows, bad = T.move_rows(SCHOOL, csv("grade.csv", "id,classId,seat\nle4a01,j2t,09\n"))
    plan, errors = T.move_plan(SCHOOL, rows, t_move)
    check("学年が変わる移動は止める", errors and "学年" in errors[0], errors)
    before = open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8").read()
    # 入れ替え：S が空けた α-02 に U が入る（同じ CSV の中なら通る）。TT は id でなく今の席で指す
    text = "id,fromClass,fromSeat,classId,seat\nle4a02,,,e4b,04\n,e4a,03,e4b,05\nle4b01,,,e4a,02\nle4a01,,,e4a,01\n"
    rows, bad = T.move_rows(SCHOOL, csv("move.csv", text))
    check("id でも今の席でも指せる", not bad and len(rows) == 4, bad)
    plan, errors = T.move_plan(SCHOOL, rows, t_move)
    check("入れ替えは通る", not errors, errors)
    check("今と同じ席の行は数えるだけ", plan["same"] == 1 and len(plan["moves"]) == 3, (plan["same"], len(plan["moves"])))
    after = open(paths.school_file(SCHOOL, "accounts.json"), encoding="utf-8").read()
    check("確かめるだけでは何も書かない", before == after)
    tr = {(a, s): op for a, s, op, _k in plan["transfers"]}
    check("α 第2回：S は写真を出しているので残す", tr.get((a2["id"], sS)) == "keep", tr.get((a2["id"], sS)))
    check("α 第2回：TT（記録なし）は外す", tr.get((a2["id"], sT)) == "out", tr.get((a2["id"], sT)))
    check("α 第2回：U を足す", tr.get((a2["id"], sU)) == "in", tr.get((a2["id"], sU)))
    check("β 第2回：S・TT を足し、U を外す",
          (tr.get((b2["id"], sS)), tr.get((b2["id"], sT)), tr.get((b2["id"], sU))) == ("in", "in", "out"),
          (tr.get((b2["id"], sS)), tr.get((b2["id"], sT)), tr.get((b2["id"], sU))))
    check("期限の過ぎた α 第1回には触らない", not any(a == a1["id"] for a, _s, _o, _k in plan["transfers"]))
    sci = [a["id"] for a in hw_of("e4:science")]
    online = [a["id"] for a in hw_of("e4o:math")]
    check("学年のコース（理科）と指名のコースには触らない",
          not any(a in sci or a in online for a, _s, _o, _k in plan["transfers"]))
    check("前のコースに残る個別の決まりを知らせる", any("個別の決まり" in n for n in plan["notes"]), plan["notes"])

    print("\n移す")
    T.move_apply(SCHOOL, plan, "m20260920-100000", t_move)
    check("S は β の 04、ログインIDと sid は同じ",
          (acc(S)["classId"], acc(S)["seat"], acc(S)["sid"]) == ("e4b", "04", sS))
    check("U は α の 02", (acc(U)["classId"], acc(U)["seat"]) == ("e4a", "02"))
    check("前の席が日付つきで残る", (acc(S).get("moves") or [{}])[-1].get("from") == {"classId": "e4a", "seat": "02"})
    check("移る前の日の席を引ける", T.class_at(acc(S), at("2026-09-15 12:00")) == ("e4a", "02"))
    check("移った後の日は今の席", T.class_at(acc(S), at("2026-09-21 12:00")) == ("e4b", "04"))
    lab = T.desk_labels(SCHOOL)
    lab0 = T.desk_labels(SCHOOL, at=at("2026-09-15 12:00"))
    check("今の名前は 小4β-04、9/15 の名前は 小4α-02", (lab[sS], lab0[sS]) == ("小4β-04", "小4α-02"), (lab[sS], lab0[sS]))
    a2n = [a for a in hw_of("e4a:math", 2)][0]
    b2n = [a for a in hw_of("e4b:math", 2)][0]
    check("α 第2回の受け取り手：S は残り、TT は外れ、U が入った",
          sS in a2n["students"] and sT not in a2n["students"] and sU in a2n["students"])
    check("β 第2回の受け取り手：S と TT が入り、U は外れた",
          sS in b2n["students"] and sT in b2n["students"] and sU not in b2n["students"])
    check("付け替えを宿題に残す（取り消しに使う）", any(e.get("sid") == sT and e.get("op") == "out"
                                                  for e in a2n.get("moved") or []))
    check("書く前の控えがある", os.path.exists(paths.backup_path(SCHOOL, "m20260920-100000", "accounts.json")))
    plans = C.all_courses(SCHOOL)
    ra = {r["sid"] for r in T.desk_roster(SCHOOL, plans["e4a:math"], T.course_asgs(T.assignments(SCHOOL), "e4a:math"), lab)}
    rb = {r["sid"] for r in T.desk_roster(SCHOOL, plans["e4b:math"], T.course_asgs(T.assignments(SCHOOL), "e4b:math"), lab)}
    check("α の成績の一覧に S・TT は出ない（U は出る）", sS not in ra and sT not in ra and sU in ra, len(ra))
    check("β の成績の一覧に S・TT が出る（U は出ない）", sS in rb and sT in rb and sU not in rb, len(rb))
    check("α の生徒の数は今のクラスの人数（01 と移ってきた U の2人）", len(ra) == 2, len(ra))
    ra_keep = {r["sid"] for r in T.desk_roster(SCHOOL, plans["e4a:math"], T.course_asgs(T.assignments(SCHOOL), "e4a:math"),
                                                 lab, keep={sS})}
    check("keep に入れれば S を残せる（本人の成績の伸び）", sS in ra_keep)
    rs = {r["sid"] for r in T.desk_roster(SCHOOL, plans["e4:science"], T.course_asgs(T.assignments(SCHOOL), "e4:science"), lab)}
    check("学年のコース（理科）には全員が残る", {sS, sT, sU} <= rs)
    check("移った後：α の「個別の宿題」に S は出ない（もう効かない）",
          not any(r["sid"] == sS for r in T.desk_board(SCHOOL, "e4a:math", plans["e4a:math"])))
    check("決まりそのものは消さない", bool(PR.rules_of(SCHOOL, "e4a:math").get(sS)))

    print("\n成績の伸び（本人）")
    T._GROWTH.clear()
    g = T.student_growth(SCHOOL, sS, now=at("2026-09-21 12:00"))
    math = [c for c in g["courses"] if c["subject"] == "math"]
    check("算数は1本", len(math) == 1, [c["keys"] for c in math])
    check("前のクラス（α）の単元が残る", math and "e4a:math" in math[0]["keys"], math and math[0]["keys"])
    check("α 第1回の評価（できました）が点として残る",
          math and any(u.get("key") == "e4a:math" and u.get("u") is not None for u in math[0]["units"]),
          math and math[0]["units"])
    check("α の移った後の空の単元は入らない",
          math and not any(u.get("key") == "e4a:math" and (u.get("date") or "") >= "2026-09-20" for u in math[0]["units"]))
    gu = T.student_growth(SCHOOL, sT, now=at("2026-09-21 12:00"))
    check("記録の無い生徒（TT）も落ちない", isinstance(gu.get("courses"), list))

    print("\n塾内テストの取り込み（テストの日の席で合わせる）")
    table = "席番号,合計\n小4α-01,80\n小4α-02,70\n小4α-03,60\n"
    got, miss = SC.match_seats(SC.parse(table), T.score_roster(SCHOOL, "e4a:math", plans["e4a:math"], "2026-09-15"))
    check("9/15 のテスト：小4α-02 は S（今その席の U ではない）", got.get("小4α-02") == sS, got.get("小4α-02"))
    check("9/15 のテスト：小4α-03 は TT（もう α にいなくても合わせる）", got.get("小4α-03") == sT, got.get("小4α-03"))
    check("9/15 のテスト：3人とも合う", not miss, miss)
    got2, miss2 = SC.match_seats(SC.parse("席番号,合計\n小4α-02,90\n"),
                                  T.score_roster(SCHOOL, "e4a:math", plans["e4a:math"], "2026-09-21"))
    check("9/21 のテスト：小4α-02 は U", got2.get("小4α-02") == sU, got2.get("小4α-02"))
    got3, miss3 = SC.match_seats(SC.parse("席番号,合計\n小4β-01,90\n"),
                                  T.score_roster(SCHOOL, "e4b:math", plans["e4b:math"], "2026-09-15"))
    check("9/15 の β のテスト：小4β-01 は U（その日は β にいた）", got3.get("小4β-01") == sU, got3.get("小4β-01"))
    got4, miss4 = SC.match_seats(SC.parse("席番号,合計\n小4β-04,50\n"),
                                  T.score_roster(SCHOOL, "e4b:math", plans["e4b:math"], "2026-09-15"))
    check("9/15 の β のテスト：その日いなかった S には入れない", not got4, got4)

    print("\n名簿の登録で、同じ席に2人を作らない")
    out = os.path.join(ROOT, "roster-out.csv")
    ns = argparse.Namespace(school=SCHOOL, file=csv("roster.csv", "classId,seat\ne4a,02\ne4b,04\ne4a,03\ne4a,09\n"),
                            out=out, yes=True)
    T.cmd_roster_import(ns)
    db = T.accounts(SCHOOL)
    check("α-02（U が移ってきた）には作らない", "le4a02b" not in db and db["le4a02"]["classId"] == "e4b")
    check("β-04（S が移ってきた）には作らない", "le4b04" not in db)
    check("α-03（TT が移って空いた）にも推測で作らない", "le4a03b" not in db and db["le4a03"]["classId"] == "e4b")
    check("新しい席 α-09 は今までどおり作る", "le4a09" in db)
    ns = argparse.Namespace(school=SCHOOL, id="le4a02x", seat="02", password="pass-word", level="e4",
                            klass="e4a", teacher=False, classes=None, assign=None)
    check("add も同じ席に2人を作らない", T.cmd_add(ns) == 1 and "le4a02x" not in T.accounts(SCHOOL))

    print("\nもう一度同じ CSV（移ったあと）")
    rows, bad = T.move_rows(SCHOOL, csv("move-again.csv", "id,classId,seat\nle4a02,e4b,04\nle4b01,e4a,02\n"))
    plan2, errors2 = T.move_plan(SCHOOL, rows, at("2026-09-20 11:00"))
    check("流し直しても何も起きない", not errors2 and not plan2["moves"], (errors2, len(plan2["moves"])))

    print("\n取り消す")
    n, errors, notes = T.move_undo(SCHOOL, "m20260920-100000", apply=False)
    check("確かめるだけ（3名）", n == 3 and not errors, (n, errors))
    check("確かめるだけでは戻さない", acc(S)["classId"] == "e4b")
    n, errors, notes = T.move_undo(SCHOOL, "m20260920-100000", apply=True)
    check("戻した", n == 3 and not errors, (n, errors))
    check("S・TT・U が元の席に", (acc(S)["classId"], acc(S)["seat"], acc(TT)["seat"], acc(U)["classId"], acc(U)["seat"])
          == ("e4a", "02", "03", "e4b", "01"))
    check("クラス替えの記録も消える", not acc(S).get("moves"))
    a2u = hw_of("e4a:math", 2)[0]
    b2u = hw_of("e4b:math", 2)[0]
    check("宿題の受け取り手も戻る",
          sT in a2u["students"] and sU not in a2u["students"] and sS not in b2u["students"]
          and sT not in b2u["students"] and sU in b2u["students"] and sS in a2u["students"])
    check("付け替えの記録も消える", not a2u.get("moved") and not b2u.get("moved"))
    check("α の個別の宿題に S が戻る",
          any(r["sid"] == sS for r in T.desk_board(SCHOOL, "e4a:math", C.all_courses(SCHOOL)["e4a:math"])))

    print("\n2回続けたクラス替えは、新しい方から取り消す")
    rows, _b = T.move_rows(SCHOOL, csv("m1.csv", "id,classId,seat\nle4a02,e4b,04\n"))
    plan, errors = T.move_plan(SCHOOL, rows, at("2026-09-20 12:00"))
    T.move_apply(SCHOOL, plan, "m20260920-120000", at("2026-09-20 12:00"))
    rows, _b = T.move_rows(SCHOOL, csv("m2.csv", "id,classId,seat\nle4a02,e4b,06\n"))
    plan, errors = T.move_plan(SCHOOL, rows, at("2026-10-25 12:00"))
    T.move_apply(SCHOOL, plan, "m20261025-120000", at("2026-10-25 12:00"))
    n, errors, notes = T.move_undo(SCHOOL, "m20260920-120000", apply=True)
    check("古い方からは取り消せない（何も変えない）", errors and acc(S)["seat"] == "06", errors)
    check("一覧に2つの番号", set(T.move_batches(SCHOOL)) == {"m20260920-120000", "m20261025-120000"})
    n, errors, notes = T.move_undo(SCHOOL, "m20261025-120000", apply=True)
    n2, errors2, notes2 = T.move_undo(SCHOOL, "m20260920-120000", apply=True)
    check("新しい方から順に取り消せる", not errors and not errors2 and acc(S)["classId"] == "e4a" and acc(S)["seat"] == "02",
          (errors, errors2, acc(S)["classId"], acc(S)["seat"]))

    print("\n控えは長く置かない")
    old = paths.backup_path(SCHOOL, "m20260101-000000", "accounts.json")
    os.makedirs(os.path.dirname(old), exist_ok=True)
    open(old, "w").write("{}")
    os.utime(os.path.dirname(old), (time.time() - 90 * 86400,) * 2)
    gone = paths.prune_backups(SCHOOL)
    check("60日より古い控えは消える", "m20260101-000000" in gone and not os.path.exists(old), gone)
    try:
        paths.backup_path(SCHOOL, "../x", "accounts.json")
        check("控えの印に ../ を通さない", False)
    except paths.BadPath:
        check("控えの印に ../ を通さない", True)

    print("\n%s。（%d件）" % ("すべて通った" if not ng_n else "× %d件" % ng_n, ok_n + ng_n))
    return 1 if ng_n else 0


if __name__ == "__main__":
    sys.exit(main())

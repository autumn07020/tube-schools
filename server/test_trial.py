#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ためし運用のデモ（demo_trial.py）が、本物の校舎の中で**見分けがつき・本物に触れず・消せる**ことを確かめる。

なぜこの検査が要るか
--------------------
本物の校舎（waseaca-london）に架空の記録を置く。静かにずれると
**本物の席に架空の記録が付く／入ったばかりの本物の生徒に架空の宿題が届く／消したつもりで残る**
という形で壊れ、目では分からない。決めごとをそのまま確かめる。

  ・受け取るのはためし用の生徒（demo の印）だけ。席（seat）は役割も記録も変わらない
  ・作った宿題・提出箱・計画に demo の印。段階は appBy=demo
  ・入ったばかりの本物の生徒（join_open_homework）は、demo の宿題には足されない
  ・--clean で、印のあるものと ためし用の生徒の記録が全部消え、計画と段階が戻る。口座は残る（--accounts で消える）
  ・2度作っても同じ数（先に片づけてから作る）
  ・見本の講師：担当でなければ作らない。作れば、きのう期限の提出箱に未評価の写真

    python3 server/test_trial.py
"""

import glob
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/tmp/test-trial"
os.environ["MYACADY_ROOT"] = ROOT
os.environ["MYACADY_FSYNC"] = "0"
os.environ["TZ"] = "Europe/London"
time.tzset()
sys.path.insert(0, HERE)
shutil.rmtree(ROOT, ignore_errors=True)

import paths                                     # noqa: E402
import lessons as L                              # noqa: E402
import courses as C                              # noqa: E402
import submissions as SUB                        # noqa: E402
import tube_server as T                          # noqa: E402
import demo_running as D                         # noqa: E402
import demo_trial as X                           # noqa: E402

SCHOOL = "waseaca-london"
ok_n = ng_n = 0


def check(name, cond, detail=""):
    global ok_n, ng_n
    if cond:
        ok_n += 1
        print("  OK   %s" % name)
    else:
        ng_n += 1
        print("  ×    %s  %s" % (name, detail))


def setup():
    paths.ensure_school(SCHOOL)
    paths.save(paths.school_file(SCHOOL, "school.json"),
               {"id": SCHOOL, "name": "検査校", "code": "w", "tz": "Europe/London"})
    paths.save(paths.school_file(SCHOOL, "curriculum.json"), {"v": 2, "classes": [
        {"id": "e4a", "name": "小4α", "grade": "e4"},
        {"id": "e4b", "name": "小4β", "grade": "e4"},
        {"id": "j3r", "name": "中3R", "grade": "j3"}]})
    D.make_materials(SCHOOL)
    # 講師（担当はコースで持つ）と、本物の席（まだ渡していない）
    T.add_account(SCHOOL, "wt01", "kensa-kensa-kensa-0001", "T01", "teacher", "", "", classes=["-"])
    T.add_account(SCHOOL, "wt02", "kensa-kensa-kensa-0002", "T02", "teacher", "", "", classes=["-"])
    T.add_account(SCHOOL, "wt03", "kensa-kensa-kensa-0003", "T03", "teacher", "", "", classes=["-"])
    for seat in ("01", "02", "03", "04", "05", "06", "07"):
        T.add_account(SCHOOL, "we4a%s" % seat, "kensa-seito-kensa-%s00" % seat, seat, "seat", "e4", "e4a")
    for seat in ("01", "02", "03"):
        T.add_account(SCHOOL, "we4b%s" % seat, "kensa-seito-kensa-%s01" % seat, seat, "seat", "e4", "e4b")
    for seat in ("02", "03", "04", "05", "06", "07"):
        T.add_account(SCHOOL, "wj3r%s" % seat, "kensa-seito-kensa-%s02" % seat, seat, "seat", "j3", "j3r")
    T.add_account(SCHOOL, "wj3r01", "kensa-seito-kensa-0100", "01", "student", "j3", "j3r")   # 在籍中の本物の生徒
    T.add_account(SCHOOL, "wdj3r91", "kensa-seito-kensa-9100", "91", "student", "j3", "j3r")  # 前の形のためし用の生徒（消える）
    db = T.accounts(SCHOOL)
    t1, t2 = db["wt01"]["sid"], db["wt02"]["sid"]
    defs = [
        ("e4a:math", {"name": "小4α 算数", "grade": "e4", "subject": "math", "teachers": [t1],
                      "slots": C.parse_slots("水18:20-19:50"), "classes": ["e4a"], "students": [],
                      "unit": "lesson", "weekday": 0, "from": "", "to": ""}),
        ("e4b:japanese", {"name": "小4β 国語", "grade": "e4", "subject": "japanese", "teachers": [t1],
                          "slots": C.parse_slots("水16:40-18:10"), "classes": ["e4b"], "students": [],
                          "unit": "lesson", "weekday": 0, "from": "", "to": ""}),
        ("j3r:math", {"name": "中3R 数学", "grade": "j3", "subject": "math", "teachers": [t1],
                      "slots": C.parse_slots("火18:20-19:50 木18:20-19:50"), "classes": ["j3r"], "students": [],
                      "unit": "lesson", "weekday": 0, "from": "", "to": ""}),
        ("j3rcatch:math", {"name": "中3R キャッチアップ講座", "grade": "j3", "subject": "math", "teachers": [t1],
                           "slots": C.parse_slots("土16:00-17:10"), "classes": [], "students": [],
                           "unit": "lesson", "weekday": 0, "from": "", "to": ""}),
        ("e4a:japanese", {"name": "小4α 国語", "grade": "e4", "subject": "japanese", "teachers": [t2],
                          "slots": C.parse_slots("月16:40-18:10"), "classes": ["e4a"], "students": [],
                          "unit": "lesson", "weekday": 0, "from": "", "to": ""}),
        ("e4:science", {"name": "小4 理科", "grade": "e4", "subject": "science", "teachers": [],
                        "slots": C.parse_slots("木16:40-18:10"), "classes": ["e4a", "e4b"], "students": [],
                        "unit": "lesson", "weekday": 0, "from": "", "to": ""}),
    ]
    C.upsert(SCHOOL, defs, new_app=False)


def demo_asgs():
    return {k: v for k, v in T.assignments(SCHOOL).items() if v.get("demo")}


def main():
    setup()
    s = X.build(SCHOOL, "wt01", weeks=6, keep=["we4a07", "wj3r07"])
    db = T.accounts(SCHOOL)
    demo = X.demo_students(db)
    sids = {a["sid"] for a in demo.values()}
    by = {}
    for lid, a in demo.items():
        by.setdefault(a.get("classId"), []).append(lid)

    check("ためしの生徒は、クラスごとに今ある席から無作為に（e4a は 5〜6 人、e4b は 3 人全部、j3r は 5〜6 人）。demo の印",
          5 <= len(by.get("e4a") or []) <= 6 and len(by.get("e4b") or []) == 3 and 5 <= len(by.get("j3r") or []) <= 6
          and all(a.get("demo") is True and a.get("role") == "student" and a.get("demoRole") == "seat" for lid, a in demo.items() if not lid.startswith("wd")),
          {k: len(v) for k, v in by.items()})
    check("在籍の本物の生徒 wj3r01 は選ばれない（席が 5 人以上あるとき）。--keep の席 we4a07 も選ばれず席のまま。前の形の wdj3r91 は消えた",
          not db["wj3r01"].get("demo") and db["wj3r01"]["role"] == "student" and db["we4a07"]["role"] == "seat" and "wdj3r91" not in db, s["cleaned"])
    check("2 度選んでも同じ人（種を固定）", sorted(demo) == sorted(X.demo_students(T.accounts(SCHOOL))))
    check("授業計画は全講師の全コース（wt01 の 4 ＋ wt02 の 1）。担当の無い 小4 理科は計画なし。印 demo。段階は全部 4（appBy=demo）",
          sorted(s["planned"]) == ["e4a:japanese", "e4a:math", "e4b:japanese", "j3r:math", "j3rcatch:math"]
          and all(L.plan(SCHOOL, k).get("demo") and L.plan(SCHOOL, k).get("use") == 4 and L.plan(SCHOOL, k).get("appBy") == "demo" for k in s["planned"]), s["planned"])
    check("ためしの生徒のクラスが受けるほかのコース（小4 理科）も 4 に（毎日テストが全教科に出る）。計画は無いまま",
          s.get("levels") == ["e4:science"] and L.plan(SCHOOL, "e4:science").get("use") == 4
          and not L.plan(SCHOOL, "e4:science").get("lessons"), (s.get("levels"), L.plan(SCHOOL, "e4:science").get("use")))
    j3 = {db[l]["sid"] for l in by.get("j3r") or []}
    check("クラスの無いコース（j3rcatch:math）は、中3R のためしの生徒を指名する",
          set(L.plan(SCHOOL, "j3rcatch:math").get("students") or []) == j3)
    asg = T.assignments(SCHOOL)
    dem = demo_asgs()
    nowms = time.time() * 1000
    past = {k: x for k, x in asg.items() if int(x.get("dueAt") or 0) < nowms}
    open_ = {k: x for k, x in asg.items() if int(x.get("dueAt") or 0) >= nowms}
    check("出した宿題がある（学期のはじめから）。全部に demo の印", len(asg) >= 20 and len(dem) == len(asg), (len(asg), len(dem)))
    check("期限の過ぎた回の受け取り手は、ためしの生徒だけ（本物の生徒に「未提出」の山を付けない）",
          past and all(set(x.get("students") or []) <= sids for x in past.values()), len(past))
    r01 = db["wj3r01"]["sid"]
    mine_open = [x for x in open_.values() if (x.get("lesson") or {}).get("key") == "j3r:math" and not x.get("quiz")]
    check("本物の生徒 wj3r01（中3R 在籍）に、**今の宿題（期限前）は届く**。過ぎた回は届かない",
          mine_open and all(r01 in (x.get("students") or []) for x in mine_open)
          and not any(r01 in (x.get("students") or []) for x in past.values()), (len(mine_open), len(past)))
    prog = glob.glob(os.path.join(paths.progress_dir(SCHOOL), "*.json"))
    check("記録（進捗）は、ためしの生徒のぶんだけ", len(prog) == len(sids) and all(os.path.basename(p).split(".")[0] in sids for p in prog), (len(prog), len(sids)))
    rt = T.ratings(SCHOOL)
    check("紙の評価がある。全部ためしの生徒", rt and all(set(per) <= sids for per in rt.values()), len(rt))
    box = [x for x in asg.values() if x.get("quiz") and (x.get("lesson") or {}).get("key") == "e4a:japanese" and not x.get("kind")]
    sdb = SUB.load(SCHOOL)
    e4a = {db[l]["sid"] for l in by.get("e4a") or []}
    check("講師 wt02 にも 1 つ、きのう期限の提出箱（小4α 国語）に ためしの生徒全員の写真。未評価",
          len(box) == 1 and set(sdb.get(box[0]["id"]) or {}) == e4a and not rt.get(box[0]["id"]) and s["picked"] == {"wt02": "e4a:japanese"}, (len(box), s.get("boxes"), s.get("picked")))
    check("本人の提出箱（漢字テスト・記述）と、返した添削・メッセージがある",
          s["quiz"] >= 1 and s["essay"] >= 1 and s["returned"] >= 1 and s["messages"] >= 1, (s["quiz"], s["essay"], s["returned"], s["messages"]))
    kk_all = [x for x in asg.values() if x.get("kind") == "過去問"]
    kk = [x for x in kk_all if (x.get("lesson") or {}).get("key") == "j3r:math"]
    top = (by.get("j3r") or [None])[0]
    kk_done = [x for x in kk if int(x.get("dueAt") or 0) < nowms]
    check("過去問 4 本（中3R 数学）。見本の生徒（先頭）には採点・添削・点数 72/100 が返っている",
          len(kk) == 4 and len(kk_done) == 2 and top and any((sdb.get(x["id"]) or {}).get(db[top]["sid"], {}).get("score") == 72 for x in kk_done), (len(kk), top))
    check("過去問は小6K には無い（高校受験に向けてゆっくり進む学年。10-12 本人）。クラス全員への箱（選んだ生徒だけではない）",
          not [x for x in kk_all if (x.get("lesson") or {}).get("key") == "e6k:math"] and all(not x.get("picked") for x in kk), len(kk_all))
    meta = T.school_meta(SCHOOL)
    pk = meta.get("trialPick") or []
    check("入口の生徒（trialPick）：学年ごとに 2 クラスの見本（e4 は e4a・e4b、j3 は j3r）＝ 3 人。どれも各クラスの先頭",
          len(pk) == 3 and all(pk_ in demo for pk_ in pk) and all(by[db[l]["classId"]][0] == l for l in pk), pk)

    # 席を使い始めた本物の生徒は、その日のうちに今の宿題（期限前）を受け取る（過ぎた回は受け取らない）
    with T.LOCK:
        db2 = T.accounts(SCHOOL)
        T.activate_seat(db2, "we4a07", by="test")
        T.save_accounts(SCHOOL, db2)
        n = T.join_open_homework(SCHOOL, ["we4a07"])
    sid07 = T.accounts(SCHOOL)["we4a07"]["sid"]
    asg2 = T.assignments(SCHOOL)
    got07 = [x for x in asg2.values() if sid07 in (x.get("students") or [])]
    check("席を使い始めた本物の生徒（小4α）は、期限前の 小4α の宿題に足される。過ぎた回には足されない",
          n >= 1 and got07 and all(int(x.get("dueAt") or 0) >= nowms and (x.get("lesson") or {}).get("key") in ("e4a:math", "e4a:japanese") for x in got07), (n, len(got07)))
    check("足しても demo の印はそのまま（片づけの目印）", all(x.get("demo") for x in got07))
    # 席を使い始めた中3R の生徒は、クラス全員への過去問（期限前の 2 本）にも足される（10-12 本人：新しい中3R の口座に過去問が無かった）
    with T.LOCK:
        db3 = T.accounts(SCHOOL)
        T.activate_seat(db3, "wj3r07", by="test")
        T.save_accounts(SCHOOL, db3)
        n3 = T.join_open_homework(SCHOOL, ["wj3r07"])
    sid3r = T.accounts(SCHOOL)["wj3r07"]["sid"]
    kk3 = [x for x in T.assignments(SCHOOL).values() if x.get("kind") == "過去問" and sid3r in (x.get("students") or [])]
    check("席を使い始めた中3R の生徒は、期限前の過去問（クラス全員の提出箱）2 本に足される。過ぎた 2 本には足されない",
          len(kk3) == 2 and all(int(x.get("dueAt") or 0) >= nowms for x in kk3), (n3, len(kk3)))

    # 2度作っても同じ
    before = (len(asg), len(rt), s["students"], s["photos"], sorted(demo))
    s2 = X.build(SCHOOL, "wt01", weeks=6, keep=["we4a07", "wj3r07"])
    after = (len(T.assignments(SCHOOL)), len(T.ratings(SCHOOL)), s2["students"], s2["photos"], sorted(X.demo_students(T.accounts(SCHOOL))))
    check("2度作っても同じ数・同じ人（先に片づけてから作る）", before == after and s2["cleaned"]["assignments"] == before[0], (before[:4], after[:4]))
    check("本物の生徒（使い始めた we4a07）の役割と記録は、作り直しても変わらない。今の宿題は作り直しても届く",
          T.accounts(SCHOOL)["we4a07"]["role"] == "student" and not os.path.exists(paths.progress_path(SCHOOL, sid07))
          and any(sid07 in (x.get("students") or []) for x in T.assignments(SCHOOL).values()), s2.get("joined"))

    # 本物の生徒が、今の宿題に写真を出した → 片づけても、その宿題は本物の宿題として残る
    keep_aid = next(k for k, x in T.assignments(SCHOOL).items() if r01 in (x.get("students") or []) and not x.get("quiz"))
    SUB.put(SCHOOL, keep_aid, r01, [{"kind": "png", "data": D._note_png(200, 260, "real")}])
    n = X.clean(SCHOOL)
    db3 = T.accounts(SCHOOL)
    rest = T.assignments(SCHOOL)
    check("--clean：ためしの宿題・提出箱・評価・写真・進捗が消える。本物の生徒の写真が付いた 1 件だけ、本物の宿題として残る（印と ためしの生徒は外れる。使い始めた wj3r07 が足されていれば残る）",
          list(rest) == [keep_aid] and r01 in (rest[keep_aid].get("students") or []) and set(rest[keep_aid].get("students") or []) <= {r01, sid3r}
          and not rest[keep_aid].get("demo")
          and not T.ratings(SCHOOL) and list(SUB.load(SCHOOL)) == [keep_aid]
          and not glob.glob(os.path.join(paths.progress_dir(SCHOOL), "*.json")), (n, list(rest)[:3]))
    check("--clean：残した宿題のコース（中3R 数学）は計画も段階もそのまま。ほかの計画は空に戻り、段階は 0。指名も外れる",
          L.plan(SCHOOL, "j3r:math").get("lessons") and L.plan(SCHOOL, "j3r:math").get("use") == 4 and not L.plan(SCHOOL, "j3r:math").get("demo")
          and all(not L.plan(SCHOOL, k).get("lessons") and not L.plan(SCHOOL, k).get("demo") for k in s["planned"] if k != "j3r:math")
          and L.plan(SCHOOL, "e4a:math").get("use") == 0 and L.plan(SCHOOL, "e4a:math").get("app") is False
          and L.plan(SCHOOL, "e4:science").get("use") == 0
          and not L.plan(SCHOOL, "j3rcatch:math").get("students"), n)
    check("--clean：選ばれていた口座は席に戻る（印も席だった印も外れる）。本物の生徒と使い始めた席は残る。入口の生徒（trialPick）も消える",
          all(db3[l]["role"] == "seat" and not db3[l].get("demo") and not db3[l].get("demoRole") for l in demo if l in db3)
          and n["restored"] == len([l for l in demo if l in db3]) and db3["wj3r01"]["role"] == "student" and db3["we4a07"]["role"] == "student"
          and not T.school_meta(SCHOOL).get("trialPick"), n)

    print("\n%s（OK %d ／ × %d）" % ("すべて通った" if not ng_n else "通っていないものがある", ok_n, ng_n))
    return 1 if ng_n else 0


if __name__ == "__main__":
    sys.exit(main())
